import random
from pathlib import Path
from typing import List, NamedTuple, Optional

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)

from src.managers.generation_manager import (
    REFERENCE_ROLE_POSE_COMPOSITION,
    GenerationError,
    Reference,
)
from src.managers.lora_library_manager import LoRALibraryError
from src.managers.prompt_assistant_manager import CharacterContext
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.comfyui_lifecycle_manager import (
    EXTERNAL_ACTIVE,
    RUNNING_OWNED,
    STARTING,
    START_FAILED,
    STOPPED,
    STOPPING,
    ComfyUILifecycleManager,
)
from src.ui.dialogs.image_preview_dialog import ImagePreviewDialog
from src.ui.dialogs.prompt_assistant_dialog import PromptAssistantDialog
from src.ui.dialogs.select_images_dialog import SelectImagesDialog
from src.ui.generation_worker import GenerationWorker

# Mission 013: images produced from this page belong to Workspace.images
# (Mission 011 ownership model) — this subfolder is a plain runtime
# destination for ComfyUIEngine's download, not a new persisted field;
# Workspace/WorkspaceStorage are untouched.
GENERATED_IMAGES_SUBFOLDER = "outputs"

# Mission 024: this page's own generic "reference strength" default
# (0-100 slider units, i.e. 0.75) — deliberately not imported from
# comfyui_workflows/comfyui_engine (InferencePage must stay ignorant of
# ComfyUI's own internal name for this concept). Coordinated by mission
# specification with the engine layer's own default, not by a shared
# import.
DEFAULT_REFERENCE_STRENGTH_PERCENT = 75

# Mission 096: this page's own copies of the exact literals
# build_txt2img_workflow()/build_img2img_workflow() have hardcoded since
# Mission 012/023 — deliberately not imported from comfyui_workflows/
# comfyui_engine (same rationale as DEFAULT_REFERENCE_STRENGTH_PERCENT
# above: InferencePage stays ignorant of the engine layer, coordinated
# by mission specification, not by a shared import — see
# MISSION_096.md section 9/10). A generation launched without touching
# any of the new controls below must reproduce the pre-Mission-096
# behavior byte-for-byte.
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 20
DEFAULT_CFG = 8
DEFAULT_SAMPLER_NAME = "euler"
DEFAULT_SCHEDULER = "normal"
DEFAULT_NEGATIVE_PROMPT = "text, watermark"

# Mission 096: width/height sanity bounds — 8 is a real, mechanical
# ComfyUI/VAE constraint (EmptyLatentImage requires multiples of 8, the
# standard SD-family latent downsampling factor), never bypassed. 64/2048
# are deliberately just UI-level sanity guardrails against an absurd
# typo, not a real hardware/ComfyUI limit — see MISSION_096.md section 4.
MIN_DIMENSION = 64
MAX_DIMENSION = 2048
DIMENSION_STEP = 8

MIN_STEPS = 1
MAX_STEPS = 150

MIN_CFG = 0.0
MAX_CFG = 30.0

# Mission 096: matches random.randint(0, 2**32 - 1), the exact range
# build_txt2img_workflow()/build_img2img_workflow() already used
# internally since Mission 012 — a QSpinBox cannot represent this range
# (Qt's native int widgets are signed 32-bit, max 2**31 - 1), so the
# fixed-seed field is a plain QLineEdit with manual validation instead
# (see _resolve_seed()) rather than silently halving the reachable range.
MIN_SEED = 0
MAX_SEED = 2**32 - 1

# Mission 096: same rationale/value as SettingsPage's own
# CHECKPOINT_DISCOVERY_TIMEOUT/LORA_DISCOVERY_TIMEOUT — a short,
# consistent timeout for an on-demand, synchronous discovery call.
SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT = 5.0


class _PendingGenerationRequest(NamedTuple):
    """
    Mission 115: an immutable snapshot of everything a generation needs,
    captured once at Generate-click time -- built by
    InferencePage._build_generation_request() and never reconstructed or
    re-read from widgets afterward, whether the generation launches
    immediately or must first wait for ComfyUI Local to start. Mirrors
    exactly the values _start_generation() already captured into local
    variables before Mission 115 (see GenerationWorker's own
    constructor) -- this only gives that existing snapshot a name and a
    place to live while a Start is in flight.
    """
    prompt_text: str
    output_directory: str
    workspace_root: str
    reference_images: List[Reference]
    reference_strength: float
    width: int
    height: int
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    negative_prompt: str
    seed: int
    lora_name: str
    lora_strength: Optional[float]
    target_engine_key: str
    target_engine: object
    checkpoint_name: Optional[str]


class InferencePage(QWidget):

    def __init__(
        self,
        generation_manager,
        workspace_manager,
        prompt_manager,
        prompt_assistant_manager,
        character_manager,
        lora_library_manager,
        application_settings_manager,
        comfyui_engine,
        forge_engine,
        comfyui_lifecycle_manager=None,
    ):
        super().__init__()

        self._generation_manager = generation_manager
        self._workspace_manager = workspace_manager
        # Mission 108: two explicit engine dependencies (already
        # constructed once by MainWindow, same stateless HTTP wrappers
        # generation_manager itself already holds) — never a dict,
        # registry, or factory. Used only to resolve which concrete
        # engine object to pass as generate()/list_checkpoints()/
        # list_samplers()/list_schedulers()'s own `engine=` override,
        # per the engine currently selected in engine_combo below.
        self._comfyui_engine = comfyui_engine
        self._forge_engine = forge_engine
        # Mission 115: the exact same ComfyUILifecycleManager instance as
        # MainWindow/SettingsPage -- never a second, private manager for
        # Inference (see main_window.py's own construction site). Falls
        # back to a private instance only when this page is constructed
        # without one (test call sites that do not exercise this
        # behavior), same convention as SettingsPage's own default.
        self.comfyui_lifecycle_manager = comfyui_lifecycle_manager or ComfyUILifecycleManager()
        self.comfyui_lifecycle_manager.state_changed.connect(
            self._on_comfyui_lifecycle_state_changed
        )
        # Mission 102: the Central LoRA Library and the ComfyUI exposure
        # path it needs (ApplicationSettings.comfyui_lora_expose_path) —
        # reused as-is, same primitives LoRAPage already calls
        # (LoRALibraryManager.list_loras()/get()/expose_to_comfyui()),
        # never a second store.
        self._lora_library_manager = lora_library_manager
        self._application_settings_manager = application_settings_manager
        # Mission 102, revised by Mission 108: two states, never
        # conflated (see GenerationManager.generate()'s own docstring)
        # — "" (explicit "no LoRA", the default, must never fall back to
        # Settings) or a real lora_id (resolved fresh via
        # lora_library_manager.get() at generation time, never cached as
        # a LoRA object — see refresh_lora_selector()/_start_generation()).
        # Mission 108 removed the third state ("use the Settings global
        # LoRA") from this interactive combo — ApplicationSettings.
        # comfyui_lora_name/comfyui_lora_strength remain readable by
        # GenerationManager's own constructor-level fallback for any
        # other caller, but InferencePage never requests it anymore, for
        # either engine.
        self._selected_lora_choice: str = ""
        # Mission 031: PromptAssistantManager is the sole Prompt Assistant
        # consumer this page ever touches — no direct AI provider
        # import here, see PromptAssistantDialog's own docstring.
        self._prompt_manager = prompt_manager
        self._prompt_assistant_manager = prompt_assistant_manager
        # Mission 034: read-only access to the Workspace's principal
        # Character, resolved only at the moment the Assistant IA
        # dialog opens (see _on_assistant_clicked) — same precedent as
        # CharactersPage(self.character_manager).
        self._character_manager = character_manager
        self._thread = None
        self._worker = None

        # Mission 083: mirrors PromptsPage/CharactersPage/LoRAPage/
        # SettingsPage's own local dirty flag (Missions 038/078) — set
        # only by real user/Assistant edits (_on_prompt_text_changed(),
        # never blocked), never by a programmatic load (set_prompt_text()
        # and the new reset_for_context_change() below both wrap their
        # own self.prompt mutation in blockSignals() and set this
        # explicitly instead).
        self._dirty = False

        # Mission 014: a successful generation no longer persists itself.
        # _pending_path is the downloaded file awaiting an explicit
        # Accept/Reject/Regenerate decision — it exists on disk (written
        # by ComfyUIEngine.download_output(), same as before) but is
        # never added to Workspace.images until Accept.
        self._pending_path = None
        self._pending_pixmap = None

        # Mission 014 final review: the workspace root active when the
        # current generation cycle (in-flight or already pending) was
        # started. A pending/in-flight result belongs exclusively to
        # this workspace context, never to whatever WorkspaceManager.
        # current_workspace happens to be later — WorkspaceManager.
        # create()/open() replace current_workspace outright, with no
        # concept of "this page has an unrelated result in flight".
        self._generation_workspace_root = None

        # Mission 022: a purely transitory reference-image selection —
        # never added to Workspace.images, never written to
        # project.json. The UI only ever holds 0 or 1 path (a plain
        # scalar is enough here); it is converted to a 0..N list only
        # at the InferencePage -> GenerationWorker boundary
        # (_start_generation()), the single point where the collection
        # representation begins. No role/semantics are attached to it.
        self._reference_image_path: Optional[str] = None

        # Mission 115: at most one generation request awaiting ComfyUI
        # Local's readiness (STOPPED/START_FAILED/STARTING at the moment
        # of the click) -- never a queue. Its identity (compared via
        # `is`, never equality) is the sole guard against a stale
        # comfyui_lifecycle_manager.state_changed signal reacting on
        # behalf of a request that was since invalidated (workspace
        # change, shutdown) or already resolved. None whenever no
        # generation is currently waiting on a ComfyUI Start.
        self._pending_generation_request: Optional[_PendingGenerationRequest] = None

        layout = QVBoxLayout(self)

        title = QLabel("Inference")
        title.setStyleSheet("font-size:24px;font-weight:bold;")

        layout.addWidget(title)

        # Mission 108: engine selector — ComfyUI (default, preserves the
        # exact pre-M108 behavior for anyone who never touches this
        # combo) / Forge. Lives directly in InferencePage, never in
        # Settings. index-to-key mapping tracked via itemData, never
        # position alone, so this stays robust to reordering.
        engine_row = QHBoxLayout()

        self.engine_label = QLabel("Moteur :")
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("ComfyUI", "comfyui")
        self.engine_combo.addItem("Forge", "forge")
        # Mission 108: tracks the last *confirmed* index — distinct from
        # engine_combo.currentIndex() itself, which the Qt widget has
        # already moved to by the time currentIndexChanged fires. A
        # blocked switch (guard refused) reverts the combo back to this
        # value; a confirmed switch updates it.
        self._engine_combo_confirmed_index = 0
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)

        engine_row.addWidget(self.engine_label)
        engine_row.addWidget(self.engine_combo)

        layout.addLayout(engine_row)

        self.generate_button = QPushButton("Générer")
        self.generate_button.clicked.connect(self._on_generate_clicked)

        layout.addWidget(self.generate_button)

        # Mission 116: transient progress indicator for the ComfyUI
        # Local auto-start handoff introduced by Mission 115 — never a
        # second error channel (QMessageBox still carries the actual
        # failure/cancellation message; this label only ever shows
        # short-lived "still waiting" text, always cleared before or
        # exactly when that dialog appears). Empty text is its idle
        # state, same convention as sampler_scheduler_status_label below.
        self.comfyui_status_label = QLabel()
        layout.addWidget(self.comfyui_status_label)

        self.prompt = QTextEdit()

        self.prompt.setPlaceholderText("Prompt...")
        self.prompt.textChanged.connect(self._on_prompt_text_changed)

        layout.addWidget(self.prompt)

        # Mission 031: Prompt Assistant minimal — InferencePage is this
        # mission's sole UI consumer of PromptAssistantManager (Option C,
        # a shared service; PromptsPage became its second consumer in
        # Mission 032, reusing the same Manager/Dialog unchanged).
        # "Enregistrer dans Prompts" is independent of the Assistant —
        # it operates on whatever text is currently
        # in self.prompt, typed manually or produced by the Assistant.
        assistant_row = QHBoxLayout()

        self.assistant_button = QPushButton("Assistant IA")
        self.assistant_button.clicked.connect(self._on_assistant_clicked)

        self.save_prompt_button = QPushButton("Enregistrer dans Prompts")
        self.save_prompt_button.setEnabled(False)
        self.save_prompt_button.clicked.connect(self._on_save_prompt_clicked)

        assistant_row.addWidget(self.assistant_button)
        assistant_row.addWidget(self.save_prompt_button)

        layout.addLayout(assistant_row)

        reference_row = QHBoxLayout()

        self.select_reference_button = QPushButton("Sélectionner une image de référence")
        self.select_reference_button.clicked.connect(self._on_select_reference_clicked)

        # Mission 086: second, independent source for the same single
        # reference primitive (self._reference_image_path) — mirrors
        # DatasetsPage's own "Importer des images" / "Ajouter depuis
        # Images…" two-button pattern rather than a menu (no QMenu
        # precedent exists anywhere else in this codebase).
        self.select_reference_from_gallery_button = QPushButton("Choisir depuis Images…")
        self.select_reference_from_gallery_button.clicked.connect(
            self._on_select_reference_from_gallery_clicked
        )

        self.reference_label = QLabel("Aucune référence sélectionnée")

        self.remove_reference_button = QPushButton("Retirer")
        self.remove_reference_button.setEnabled(False)
        self.remove_reference_button.clicked.connect(self._on_remove_reference_clicked)

        reference_row.addWidget(self.select_reference_button)
        reference_row.addWidget(self.select_reference_from_gallery_button)
        reference_row.addWidget(self.reference_label)
        reference_row.addWidget(self.remove_reference_button)

        layout.addLayout(reference_row)

        # Mission 024: visible but disabled while no reference is
        # selected (discoverability, stable layout — same treatment as
        # remove_reference_button), enabled once a reference is
        # selected. Purely transitory: never persisted (project.json or
        # ApplicationSettings), reset to the default alongside the
        # reference selection itself (_clear_reference_selection()).
        strength_row = QHBoxLayout()

        self.reference_strength_label = QLabel("Force de transformation :")

        self.reference_strength_slider = QSlider(Qt.Horizontal)
        self.reference_strength_slider.setRange(0, 100)
        self.reference_strength_slider.setValue(DEFAULT_REFERENCE_STRENGTH_PERCENT)
        self.reference_strength_slider.setEnabled(False)
        self.reference_strength_slider.valueChanged.connect(self._on_reference_strength_changed)

        self.reference_strength_value_label = QLabel(
            self._format_reference_strength(DEFAULT_REFERENCE_STRENGTH_PERCENT)
        )

        strength_row.addWidget(self.reference_strength_label)
        strength_row.addWidget(self.reference_strength_slider)
        strength_row.addWidget(self.reference_strength_value_label)

        layout.addLayout(strength_row)

        # Mission 096: real generation parameters, replacing Mission
        # 012's fixed demonstration workflow — see MISSION_096.md.
        # width/height are only meaningful on the txt2img path (no
        # reference selected): build_img2img_workflow() derives the
        # latent's dimensions from the reference image itself, so these
        # two fields are disabled the moment a reference becomes active
        # (_apply_selected_reference()/_clear_reference_selection()
        # below), mirroring reference_strength_slider's own enable/
        # disable treatment above but in the opposite direction.
        resolution_row = QHBoxLayout()

        self.width_label = QLabel("Largeur :")
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(MIN_DIMENSION, MAX_DIMENSION)
        self.width_spinbox.setSingleStep(DIMENSION_STEP)
        self.width_spinbox.setValue(DEFAULT_WIDTH)

        self.height_label = QLabel("Hauteur :")
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(MIN_DIMENSION, MAX_DIMENSION)
        self.height_spinbox.setSingleStep(DIMENSION_STEP)
        self.height_spinbox.setValue(DEFAULT_HEIGHT)

        resolution_row.addWidget(self.width_label)
        resolution_row.addWidget(self.width_spinbox)
        resolution_row.addWidget(self.height_label)
        resolution_row.addWidget(self.height_spinbox)

        layout.addLayout(resolution_row)

        # Mission 108: checkpoint selection — common to both engines,
        # editable (same style as sampler_combo/scheduler_combo below).
        # Empty at construction and after every engine change (see
        # _on_engine_changed()/_invalidate_capabilities()); populated
        # only by the shared "Rafraîchir" button below, which discovers
        # against whichever engine is currently active. Resolution at
        # Generate time (_validate_generation_parameters()/
        # _start_generation()): a non-empty value is always forwarded
        # explicitly; an empty value falls back to GenerationManager's
        # own historical ComfyUI-only constructor default for ComfyUI,
        # but blocks generation outright for Forge (no equivalent
        # cross-engine fallback exists, or ever should).
        checkpoint_row = QHBoxLayout()

        self.checkpoint_label = QLabel("Checkpoint :")
        self.checkpoint_combo = QComboBox()
        self.checkpoint_combo.setEditable(True)

        checkpoint_row.addWidget(self.checkpoint_label)
        checkpoint_row.addWidget(self.checkpoint_combo)

        layout.addLayout(checkpoint_row)

        # Mission 102: LoRA selection — two always-visible options since
        # Mission 108 removed the "use the Settings global LoRA" entry
        # (never a hidden "has the user touched this" tracking, see
        # MISSION_102.md section 3.1 / MISSION_108.md section 3.1). Real
        # entries are populated by refresh_lora_selector() below, called
        # once at the end of this constructor and again on every
        # LORA_LIBRARY_IMPORTED/DELETED/UPDATED event (wired in
        # main_window.py).
        lora_row = QHBoxLayout()

        self.lora_label = QLabel("LoRA :")
        self.lora_combo = QComboBox()
        self.lora_combo.currentIndexChanged.connect(self._on_lora_selection_changed)

        self.lora_strength_label = QLabel("Force du LoRA :")
        self.lora_strength_spinbox = QDoubleSpinBox()
        self.lora_strength_spinbox.setRange(0.0, 2.0)
        self.lora_strength_spinbox.setSingleStep(0.05)
        self.lora_strength_spinbox.setValue(1.0)
        self.lora_strength_spinbox.setEnabled(False)

        lora_row.addWidget(self.lora_label)
        lora_row.addWidget(self.lora_combo)
        lora_row.addWidget(self.lora_strength_label)
        lora_row.addWidget(self.lora_strength_spinbox)

        layout.addLayout(lora_row)

        # Mission 110: read-only display of the selected LoRA's
        # trigger_word plus an explicit (never automatic) action to
        # insert it into the prompt. Recomputed from a fresh
        # LoRALibraryManager.get() call by _refresh_lora_trigger_widgets()
        # at the two existing points that already make
        # self._selected_lora_choice vary — never a cached value.
        trigger_row = QHBoxLayout()

        self.lora_trigger_label = QLabel("")
        self.insert_lora_trigger_button = QPushButton("Insérer le trigger")
        self.insert_lora_trigger_button.setEnabled(False)
        self.insert_lora_trigger_button.clicked.connect(
            self.insert_selected_lora_trigger_into_prompt
        )

        trigger_row.addWidget(self.lora_trigger_label)
        trigger_row.addWidget(self.insert_lora_trigger_button)

        layout.addLayout(trigger_row)

        self.refresh_lora_selector()

        sampling_row = QHBoxLayout()

        self.steps_label = QLabel("Steps :")
        self.steps_spinbox = QSpinBox()
        self.steps_spinbox.setRange(MIN_STEPS, MAX_STEPS)
        self.steps_spinbox.setValue(DEFAULT_STEPS)

        self.cfg_label = QLabel("CFG :")
        self.cfg_spinbox = QDoubleSpinBox()
        self.cfg_spinbox.setRange(MIN_CFG, MAX_CFG)
        self.cfg_spinbox.setSingleStep(0.5)
        self.cfg_spinbox.setValue(DEFAULT_CFG)

        sampling_row.addWidget(self.steps_label)
        sampling_row.addWidget(self.steps_spinbox)
        sampling_row.addWidget(self.cfg_label)
        sampling_row.addWidget(self.cfg_spinbox)

        layout.addLayout(sampling_row)

        # Mission 096: sampler_name/scheduler are populated by real
        # discovery against the running ComfyUI server (GET
        # /object_info/KSampler, via GenerationManager.list_samplers()/
        # list_schedulers() — never a list hardcoded in this codebase,
        # see MISSION_096.md section 6). Editable QComboBox: usable by
        # typing even before any successful discovery, or if ComfyUI is
        # unreachable — pre-filled with the exact compatibility default
        # ("euler"/"normal") either way.
        sampler_scheduler_row = QHBoxLayout()

        self.sampler_label = QLabel("Sampler :")
        self.sampler_combo = QComboBox()
        self.sampler_combo.setEditable(True)
        self.sampler_combo.addItem(DEFAULT_SAMPLER_NAME)

        self.scheduler_label = QLabel("Scheduler :")
        self.scheduler_combo = QComboBox()
        self.scheduler_combo.setEditable(True)
        self.scheduler_combo.addItem(DEFAULT_SCHEDULER)

        self.refresh_sampler_scheduler_button = QPushButton("Rafraîchir")
        self.refresh_sampler_scheduler_button.clicked.connect(
            self._on_refresh_sampler_scheduler_clicked
        )

        sampler_scheduler_row.addWidget(self.sampler_label)
        sampler_scheduler_row.addWidget(self.sampler_combo)
        sampler_scheduler_row.addWidget(self.scheduler_label)
        sampler_scheduler_row.addWidget(self.scheduler_combo)
        sampler_scheduler_row.addWidget(self.refresh_sampler_scheduler_button)

        layout.addLayout(sampler_scheduler_row)

        self.sampler_scheduler_status_label = QLabel()

        layout.addWidget(self.sampler_scheduler_status_label)

        negative_prompt_row = QHBoxLayout()

        self.negative_prompt_label = QLabel("Prompt négatif :")
        self.negative_prompt_edit = QLineEdit()
        self.negative_prompt_edit.setText(DEFAULT_NEGATIVE_PROMPT)

        negative_prompt_row.addWidget(self.negative_prompt_label)
        negative_prompt_row.addWidget(self.negative_prompt_edit)

        layout.addLayout(negative_prompt_row)

        # Mission 096: two explicit seed usages — random (default,
        # reproduces the pre-Mission-096 behavior) and fixed/reproducible.
        # seed_edit is a plain QLineEdit rather than a QSpinBox: Qt's
        # native int widgets are signed 32-bit (max 2**31 - 1), too small
        # to represent the full random.randint(0, 2**32 - 1) range this
        # codebase has always used — see MIN_SEED/MAX_SEED above and
        # _resolve_seed() below for the manual validation this implies.
        seed_row = QHBoxLayout()

        self.random_seed_checkbox = QCheckBox("Seed aléatoire")
        self.random_seed_checkbox.setChecked(True)
        self.random_seed_checkbox.toggled.connect(self._on_random_seed_toggled)

        self.seed_label = QLabel("Seed fixe :")
        self.seed_edit = QLineEdit()
        self.seed_edit.setEnabled(False)

        seed_row.addWidget(self.random_seed_checkbox)
        seed_row.addWidget(self.seed_label)
        seed_row.addWidget(self.seed_edit)

        layout.addLayout(seed_row)

        self.seed_used_label = QLabel("Seed utilisé : —")

        layout.addWidget(self.seed_used_label)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)

        layout.addWidget(self.preview_label)

        validation_buttons = QHBoxLayout()

        self.accept_button = QPushButton("Accepter")
        self.accept_button.clicked.connect(self._on_accept_clicked)
        self.accept_button.setEnabled(False)

        self.reject_button = QPushButton("Rejeter")
        self.reject_button.clicked.connect(self._on_reject_clicked)
        self.reject_button.setEnabled(False)

        self.regenerate_button = QPushButton("Régénérer")
        self.regenerate_button.clicked.connect(self._on_regenerate_clicked)
        self.regenerate_button.setEnabled(False)

        self.preview_enlarge_button = QPushButton("Voir en grand")
        self.preview_enlarge_button.clicked.connect(self._on_enlarge_clicked)
        self.preview_enlarge_button.setEnabled(False)

        validation_buttons.addWidget(self.accept_button)
        validation_buttons.addWidget(self.reject_button)
        validation_buttons.addWidget(self.regenerate_button)
        validation_buttons.addWidget(self.preview_enlarge_button)

        layout.addLayout(validation_buttons)

    def _on_generate_clicked(self):

        prompt_text = self.prompt.toPlainText()

        if not prompt_text.strip():
            QMessageBox.warning(
                self,
                "Prompt vide",
                "Saisissez un prompt avant de générer."
            )
            return

        if not self._workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de générer."
            )
            return

        if not self._validate_generation_parameters():
            return

        self._start_generation(prompt_text)

    def _validate_generation_parameters(self) -> bool:
        """
        Mission 096: shared precondition check for both
        _on_generate_clicked() and _on_regenerate_clicked() — called
        before either one commits to starting a generation, in
        particular before _on_regenerate_clicked() discards the
        still-pending previous result (see its own call site below), so
        an invalid value here never destroys a result the architect
        could otherwise still Accept/Reject. Pure validation, no
        resolution: never consumes a random seed draw (see
        _resolve_seed(), only ever called from _start_generation()
        itself, exactly once per actual generation attempt).

        width/height are only checked when no reference is active —
        MISSION_096.md section 3/10: they have no effect on the img2img
        path (build_img2img_workflow() has no such parameters), so
        validating them there would only ever produce a confusing
        rejection for a field the generation about to run does not use.
        """
        if self._reference_image_path is None:
            width = self.width_spinbox.value()
            height = self.height_spinbox.value()
            if width % DIMENSION_STEP != 0 or height % DIMENSION_STEP != 0:
                QMessageBox.warning(
                    self,
                    "Résolution invalide",
                    f"La largeur et la hauteur doivent être des multiples de {DIMENSION_STEP}."
                )
                return False

        if not self.random_seed_checkbox.isChecked():
            text = self.seed_edit.text().strip()
            if not text.isdigit() or not (MIN_SEED <= int(text) <= MAX_SEED):
                QMessageBox.warning(
                    self,
                    "Seed invalide",
                    f"Le seed fixe doit être un entier compris entre {MIN_SEED} et {MAX_SEED}."
                )
                return False

        # Mission 108: Forge has no cross-engine checkpoint fallback —
        # GenerationManager's own constructor-level default
        # (self._checkpoint_name) is read once from
        # ApplicationSettings.comfyui_checkpoint_name and must never
        # silently cross the ComfyUI/Forge boundary (MISSION_108.md
        # section 3.4). Checked here, not in _start_generation(), for
        # the same reason width/height/seed are checked here — an
        # invalid state must never destroy a still-pending previous
        # result (see this method's own docstring and
        # _on_regenerate_clicked(), which clears the pending result only
        # after this check passes).
        if self._active_engine_key() == "forge" and not self.checkpoint_combo.currentText().strip():
            QMessageBox.warning(
                self,
                "Checkpoint requis",
                "Sélectionnez un checkpoint Forge avant de générer — cliquez sur "
                "Rafraîchir pour découvrir les checkpoints disponibles."
            )
            return False

        return True

    def _active_engine_key(self) -> str:
        """
        Mission 108: "comfyui" or "forge" — the itemData of
        engine_combo's current selection, never inferred from position
        alone (see engine_combo's own construction).
        """
        return self.engine_combo.currentData()

    def _active_engine(self):
        """
        Mission 108: the concrete engine instance (ComfyUIEngine/
        ForgeEngine, both duck-typed, never isinstance-checked) matching
        _active_engine_key() — the one object forwarded as generate()/
        list_checkpoints()/list_samplers()/list_schedulers()'s own
        `engine=` override.
        """
        if self._active_engine_key() == "forge":
            return self._forge_engine
        return self._comfyui_engine

    def _on_lora_selection_changed(self, index: int):
        # Mission 102: itemData is already exactly the value generate()
        # needs — None, "", or a real lora_id — see refresh_lora_selector().
        choice = self.lora_combo.itemData(index)
        self._selected_lora_choice = choice
        # A real lora_id is the only truthy value among the three states.
        self.lora_strength_spinbox.setEnabled(bool(choice))
        self._refresh_lora_trigger_widgets()

    def refresh_lora_selector(self, _payload=None, target_lora_id: Optional[str] = None):
        """
        Mission 102, revised by Mission 108: rebuilds the LoRA combo
        from the Central LoRA Library's real current entries — called
        once at construction and on every LORA_LIBRARY_IMPORTED/DELETED/
        UPDATED event (wired in main_window.py, same convention as
        LoRAPage.update_central_library(), payload always ignored in
        favor of a full re-read).

        Mission 108: the combo now has exactly two kinds of entries —
        "Aucun LoRA" (itemData="", index 0, the default) and one entry
        per real Central Library LoRA (itemData=lora_id) — identical
        for both engines. The "Utiliser le réglage global (Settings)"
        entry (itemData=None) is gone entirely from this interactive
        combo; ApplicationSettings.comfyui_lora_name/comfyui_lora_strength
        remain untouched for any other caller, simply never requested by
        InferencePage anymore.

        Preserves the current selection across a rename (matched by
        lora_id, so the displayed label follows LoRA.name automatically).
        If the previously selected real LoRA is no longer in the Library
        (deleted), the selection falls back explicitly to "Aucun LoRA"
        — never a dangling lora_id left selected (MISSION_102.md section
        3.3).

        Mission 109: target_lora_id is a keyword-only-in-practice
        parameter, never supplied by the 3 EventBus subscriptions above
        (each calls this with only their positional payload, so
        target_lora_id stays None for them — behavior strictly
        unchanged). It exists solely for the explicit Training →
        Inference handoff (MainWindow._on_training_use_lora_in_inference):
        when given and present among the entries just rebuilt, it takes
        priority over previous_choice; otherwise (absent, None, or
        matching no rebuilt entry) this falls through to the
        previous_choice/"Aucun LoRA" logic exactly as before.
        """
        previous_choice = self._selected_lora_choice
        loras = self._lora_library_manager.list_loras()
        lora_ids = {lora.lora_id for lora in loras}

        self.lora_combo.blockSignals(True)
        self.lora_combo.clear()
        self.lora_combo.addItem("Aucun LoRA", "")
        for lora in loras:
            self.lora_combo.addItem(lora.name, lora.lora_id)

        if target_lora_id and target_lora_id in lora_ids:
            restored_index = self.lora_combo.findData(target_lora_id)
        elif previous_choice and previous_choice in lora_ids:
            restored_index = self.lora_combo.findData(previous_choice)
        else:
            restored_index = 0

        self.lora_combo.setCurrentIndex(restored_index)
        self.lora_combo.blockSignals(False)

        self._selected_lora_choice = self.lora_combo.itemData(restored_index)
        self.lora_strength_spinbox.setEnabled(bool(self._selected_lora_choice))
        self._refresh_lora_trigger_widgets()

    def _refresh_lora_trigger_widgets(self):
        """
        Mission 110: recomputes the read-only trigger_word display and
        the insert-into-prompt action's enabled state from a fresh
        LoRALibraryManager.get() call — never a value cached from a
        previous selection. Called from the two existing points that
        already make self._selected_lora_choice vary
        (_on_lora_selection_changed(), refresh_lora_selector()).
        """
        lora = None
        if self._selected_lora_choice:
            lora = self._lora_library_manager.get(self._selected_lora_choice)

        trigger_word = lora.trigger_word if lora else ""
        self.lora_trigger_label.setText(trigger_word)
        self.insert_lora_trigger_button.setEnabled(bool(trigger_word))

    def insert_selected_lora_trigger_into_prompt(self):
        """
        Mission 110: explicit, user-triggered insertion only — never
        called automatically (not from refresh_lora_selector(), not from
        the Mission 109 Training -> Inference handoff mediator). Rereads
        the trigger fresh rather than trusting the label's current text.
        Never replaces or rewrites the existing prompt.

        Duplicate check (architect-confirmed rule): the prompt is split
        on ",", each element is stripped, and the trigger is considered
        already present only on an exact, case-sensitive match against
        one of those elements -- never a substring search, never a
        case-insensitive comparison.
        """
        lora = None
        if self._selected_lora_choice:
            lora = self._lora_library_manager.get(self._selected_lora_choice)

        trigger_word = lora.trigger_word if lora else ""
        if not trigger_word:
            return

        current_prompt = self.prompt_text()
        existing_elements = [part.strip() for part in current_prompt.split(",")]
        if trigger_word in existing_elements:
            return

        if not current_prompt.strip():
            new_prompt = trigger_word
        else:
            new_prompt = f"{trigger_word}, {current_prompt}"

        self.set_prompt_text(new_prompt)

    def _resolve_seed(self) -> int:
        """
        Mission 096: the one point where "random" resolves to a
        concrete int — called only from _start_generation(), after
        _validate_generation_parameters() has already confirmed a
        fixed-mode value (if any) is valid, so the int(...) conversion
        below can never fail here. Random mode uses the exact same
        random.randint(0, 2**32 - 1) range build_txt2img_workflow()/
        build_img2img_workflow() already used internally since Mission
        012 — resolving it here (rather than leaving it to those
        functions' own internal fallback) is what lets InferencePage
        display the value actually used (MISSION_096.md section 5)
        without any change to their return type.
        """
        if self.random_seed_checkbox.isChecked():
            return random.randint(MIN_SEED, MAX_SEED)
        return int(self.seed_edit.text().strip())

    def _on_prompt_text_changed(self):
        # Mission 083: only ever connected to textChanged, so this never
        # fires during a programmatic load protected by
        # self.prompt.blockSignals() (set_prompt_text(),
        # reset_for_context_change()) — genuine manual typing and the
        # Prompt Assistant's result injection (_on_assistant_clicked(),
        # deliberately left unblocked, same precedent as PromptsPage) are
        # the only two ways this can run, and both must mark the prompt
        # dirty.
        self._dirty = True
        self.save_prompt_button.setEnabled(bool(self.prompt.toPlainText().strip()))

    def _on_assistant_clicked(self):
        # Mission 034: the single conversion point (CharacterContext.from_character)
        # is called identically here and in PromptsPage — no separate
        # construction logic duplicated between the two Pages.
        character_context = CharacterContext.from_character(self._character_manager.principal_character)

        dialog = PromptAssistantDialog(
            self._prompt_assistant_manager,
            existing_prompt=self.prompt.toPlainText(),
            character_context=character_context,
            parent=self,
        )

        if dialog.exec() == QDialog.Accepted and dialog.result_text is not None:
            self.prompt.setPlainText(dialog.result_text)

    def _on_save_prompt_clicked(self):

        text = self.prompt.toPlainText()

        if not text.strip():
            return

        # Mission 031: same non-empty-name guard as
        # PromptsPage.create_prompt() — reproduced identically rather
        # than factored out (PromptManager never validates business
        # content, and a shared UI helper for one line would be
        # disproportionate — see Mission 031 specification).
        name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

        if not ok or not name.strip():
            return

        if self._save_prompt_as_new(name.strip(), text):
            # Mission 083: the text just became a persisted Prompt — the
            # page's own draft is no longer unsaved work from the
            # dirty-state guard's point of view. A further edit marks it
            # dirty again normally via _on_prompt_text_changed().
            self._dirty = False

    def _save_prompt_as_new(self, name: str, text: str) -> bool:
        """
        Mission 083: the single create()+error-handling primitive shared
        by _on_save_prompt_clicked() (name always confirmed non-empty
        beforehand) and confirm_context_change() (same). Deliberately
        does not touch self._dirty nor show any success feedback — both
        callers decide that for themselves; this only creates the Prompt
        and reports whether it succeeded, showing the appropriate
        QMessageBox on either failure path.

        create(name, text=...) — deliberately never select()/
        update_text() afterward: this must never change PromptManager.
        active_prompt_id nor PromptsPage's current selection (see
        Mission 031 specification, pre-implementation verification 2).
        """
        try:
            prompt = self._prompt_manager.create(name, text=text)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le nouveau prompt dans le projet : {exc}\n"
                "Le prompt n'a pas été créé."
            )
            return False

        if prompt is None:
            # Mission 036: distinguish "no Workspace open" from "Workspace
            # open without a principal Character" — both make create()
            # return None. Already has workspace_manager (Mission 013),
            # no new dependency needed.
            if not self._workspace_manager.opened:
                QMessageBox.warning(
                    self,
                    "Aucun projet ouvert",
                    "Ouvrez ou créez un projet avant d'enregistrer un prompt."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aucun personnage",
                    "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant d'enregistrer un prompt."
                )
            return False

        return True

    def _build_generation_request(self, prompt_text) -> Optional[_PendingGenerationRequest]:
        """
        Mission 096, restructured by Mission 115: the exact snapshot
        _start_generation() used to build directly into a
        GenerationWorker is now captured once into an immutable
        _PendingGenerationRequest, so it can either launch immediately
        or wait for ComfyUI Local's readiness without ever being rebuilt
        or re-read from widgets later (see _start_generation()/
        _launch_generation_worker() below). Returns None only on the
        pre-existing LoRA-resolution failure paths, which already show
        their own QMessageBox and leave the page untouched — callers
        must treat None as "already handled, nothing further to do".
        """
        workspace_root = str(self._workspace_manager.current_workspace.root)
        output_directory = str(Path(workspace_root) / GENERATED_IMAGES_SUBFOLDER)

        self._generation_workspace_root = workspace_root

        # Mission 022: the only point where the UI's singular selection
        # becomes a 0..N collection — captured here, before the worker
        # is even constructed, so nothing done to self._reference_image_path
        # afterward (removed, replaced) can ever reach this cycle. A
        # fresh list is built on every call, never mutated afterward.
        # Mission 056: the single element is now an explicit typed
        # Reference (role=pose_composition, the only role with a real
        # generation mechanism today) rather than a bare path — this
        # page is the primitive's real production consumer, not just a
        # legacy caller GenerationManager.generate() happens to still
        # accept.
        reference_images = (
            [Reference(self._reference_image_path, REFERENCE_ROLE_POSE_COMPOSITION)]
            if self._reference_image_path
            else []
        )

        # Mission 024: read fresh at call time, like reference_images
        # above — GenerationManager only ever uses this value when a
        # reference is actually present, so it is harmless to always
        # pass it regardless of whether one is selected.
        reference_strength = self.reference_strength_slider.value() / 100.0

        # Mission 096: read fresh at call time, same rationale as
        # reference_strength above. width/height are always read and
        # forwarded regardless of reference_images — GenerationManager/
        # ComfyUIEngine.generate_image() already never pass them into
        # build_img2img_workflow() (see MISSION_096.md section 3/10), so
        # forwarding them unconditionally here has no effect on that
        # path rather than requiring this method to know about it too.
        width = self.width_spinbox.value()
        height = self.height_spinbox.value()
        steps = self.steps_spinbox.value()
        cfg = self.cfg_spinbox.value()

        # Mission 108: target_engine resolved once, used for every
        # engine-dependent decision below (sampler/scheduler fallback,
        # checkpoint resolution, LoRA exposure, and the generate() call
        # itself) — a single source of truth for "which engine is this
        # specific generation for", never re-derived inconsistently.
        target_engine_key = self._active_engine_key()
        target_engine = self._active_engine()

        # Mission 108: ComfyUI keeps its exact historical fallback
        # (DEFAULT_SAMPLER_NAME/DEFAULT_SCHEDULER, this page's own
        # ComfyUI-flavored literals — see their own module-level
        # comment) when the combo is left empty. Forge has no
        # equivalent — falling back to a ComfyUI-cased default here
        # would silently send a ComfyUI value as a Forge selection
        # (MISSION_108.md section 3.6), so an empty combo simply
        # forwards an empty string, and Forge's own API surfaces a
        # clear error if that turns out to be unusable — never a
        # pre-flight block here (unlike checkpoint, section 3.4/6.2),
        # since only checkpoint has no engine-side auto-resolution.
        if target_engine_key == "comfyui":
            sampler_name = self.sampler_combo.currentText().strip() or DEFAULT_SAMPLER_NAME
            scheduler = self.scheduler_combo.currentText().strip() or DEFAULT_SCHEDULER
        else:
            sampler_name = self.sampler_combo.currentText().strip()
            scheduler = self.scheduler_combo.currentText().strip()

        negative_prompt = self.negative_prompt_edit.text()

        # Mission 108: a non-empty checkpoint_combo value is always
        # forwarded explicitly, for either engine. An empty value is
        # only ever reachable here for ComfyUI — Forge's own case is
        # already blocked earlier by _validate_generation_parameters(),
        # called by every caller of this method before it ever runs.
        # Omitting checkpoint_name entirely (rather than passing None)
        # lets GenerationManager fall back to its own historical
        # ComfyUI-only constructor default byte-for-byte (MISSION_108.md
        # section 3.4) — this method never reads
        # ApplicationSettings.comfyui_checkpoint_name itself.
        checkpoint_name = self.checkpoint_combo.currentText().strip() or None

        # Mission 096: the one and only resolution point — see
        # _resolve_seed()'s own docstring. Displayed immediately (before
        # the generation has even started, let alone finished) so the
        # architect can see which seed is in flight, and so it stays
        # visible as "the seed of the last attempt" even if this
        # generation goes on to fail.
        seed = self._resolve_seed()
        self.seed_used_label.setText(f"Seed utilisé : {seed}")

        # Mission 102, revised by Mission 108: resolved before anything
        # is locked/started, so a failure here (missing LoRA, exposure
        # error) leaves the page exactly as it was — no controls
        # disabled, no thread started. Two states only, since Mission
        # 108 removed the "use the Settings global LoRA" state from this
        # combo — see refresh_lora_selector()'s own docstring.
        if not self._selected_lora_choice:
            lora_name = ""
            lora_strength = None
        else:
            lora = self._lora_library_manager.get(self._selected_lora_choice)
            if lora is None:
                self.refresh_lora_selector()
                QMessageBox.warning(
                    self,
                    "LoRA introuvable",
                    "Le LoRA sélectionné n'existe plus dans la Bibliothèque — "
                    "sélection réinitialisée sur « Aucun LoRA »."
                )
                return None

            # Mission 108: which physical root/exposure call is used
            # depends on the target engine — the logical LoRA selection
            # itself stays the single self._selected_lora_choice above,
            # entirely independent of the engine (MISSION_108.md section
            # 3.3).
            if target_engine_key == "forge":
                expose_root = self._application_settings_manager.settings.forge_lora_expose_path
                expose = self._lora_library_manager.expose_to_forge
                engine_label = "Forge"
            else:
                expose_root = self._application_settings_manager.settings.comfyui_lora_expose_path
                expose = self._lora_library_manager.expose_to_comfyui
                engine_label = "ComfyUI"

            try:
                exposure = expose(lora, expose_root)
            except LoRALibraryError as exc:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'exposer ce LoRA à {engine_label} : {exc}"
                )
                return None

            lora_name = exposure.alias_name
            lora_strength = self.lora_strength_spinbox.value()

        return _PendingGenerationRequest(
            prompt_text=prompt_text,
            output_directory=output_directory,
            workspace_root=workspace_root,
            reference_images=reference_images,
            reference_strength=reference_strength,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            negative_prompt=negative_prompt,
            seed=seed,
            lora_name=lora_name,
            lora_strength=lora_strength,
            target_engine_key=target_engine_key,
            target_engine=target_engine,
            checkpoint_name=checkpoint_name,
        )

    def _start_generation(self, prompt_text):
        """
        Mission 115: for ComfyUI, a generation no longer necessarily
        launches immediately — if ComfyUI Local is not already
        RUNNING_OWNED/EXTERNAL_ACTIVE, the snapshot below is held as
        self._pending_generation_request while comfyui_lifecycle_manager
        starts it (or attaches to a Start already in flight), and is
        only handed to _launch_generation_worker() once
        _on_comfyui_lifecycle_state_changed() observes readiness. Forge
        is entirely unaffected — it always launches immediately, exactly
        as before this mission.
        """
        request = self._build_generation_request(prompt_text)
        if request is None:
            return

        if request.target_engine_key != "comfyui":
            self._launch_generation_worker(request)
            return

        state = self.comfyui_lifecycle_manager.state

        if state in (RUNNING_OWNED, EXTERNAL_ACTIVE):
            self._launch_generation_worker(request)
            return

        if state == STOPPING:
            QMessageBox.warning(
                self,
                "ComfyUI en cours d'arrêt",
                "ComfyUI est en cours d'arrêt — réessayez une fois l'arrêt terminé."
            )
            return

        # STOPPED / START_FAILED / STARTING: hold this request and
        # either engage a new Start or attach to one already in flight.
        # comfyui_lifecycle_manager.start() itself would already be a
        # no-op while STARTING (see its own guard), but it is
        # deliberately not even called in that case here, so a second
        # Start is never requested at all — only ever attached to.
        self.generate_button.setEnabled(False)
        self._set_generation_controls_enabled(False)
        self._set_validation_buttons_enabled(False)
        self._pending_generation_request = request

        if state == STARTING:
            self.comfyui_status_label.setText(
                "Un démarrage de ComfyUI est déjà en cours…"
            )
        else:
            self.comfyui_status_label.setText("Démarrage de ComfyUI en cours…")
            settings = self._application_settings_manager.settings
            self.comfyui_lifecycle_manager.start(
                settings.comfyui_path,
                settings.comfyui_install_path,
                settings.comfyui_url,
            )

    def _on_comfyui_lifecycle_state_changed(self, state):
        """
        Mission 115: the sole readiness signal Inference listens to — no
        second HTTP polling loop is ever introduced here. A no-op
        whenever no generation is currently waiting
        (self._pending_generation_request is None), which is also what
        protects this page from reacting to a state_changed caused by
        Settings' own Start/Stop buttons, or to a stale pending already
        invalidated by a workspace change/shutdown (see
        reset_for_workspace_change()/shutdown()).
        """
        request = self._pending_generation_request
        if request is None:
            return

        if state in (RUNNING_OWNED, EXTERNAL_ACTIVE):
            self._pending_generation_request = None
            self._launch_generation_worker(request)
            return

        if state == START_FAILED:
            self._abort_pending_generation(
                "Erreur de démarrage ComfyUI",
                self.comfyui_lifecycle_manager.last_error_message
                or "Échec du démarrage de ComfyUI.",
            )
            return

        if state == STOPPED:
            # Only reachable here via STARTING -> STOPPING -> STOPPED —
            # a Stop requested elsewhere (e.g. Settings) while this page
            # was waiting. start() always moves off STOPPED (to STARTING
            # or EXTERNAL_ACTIVE) before returning, so this is never a
            # redundant abort right after the pending request above was
            # just created.
            self._abort_pending_generation(
                "Démarrage annulé",
                "Le démarrage de ComfyUI a été annulé avant readiness — "
                "la génération n'a pas été lancée.",
            )
            return

        # STARTING/STOPPING: still waiting, nothing to do yet.

    def _abort_pending_generation(self, title, message):
        """
        Mirrors _on_generation_failed()'s own UI-restoration contract
        (re-enable Generate/generation controls, exactly one QMessageBox)
        for a generation that never actually reached GenerationManager.
        message is always reused as-is from ComfyUILifecycleManager
        (last_error_message) or authored once here for the Stop-while-
        waiting case — never a second, independently invented technical
        error.
        """
        self._pending_generation_request = None
        self.comfyui_status_label.clear()
        self.generate_button.setEnabled(True)
        self._set_generation_controls_enabled(True)
        QMessageBox.critical(self, title, message)

    def _launch_generation_worker(self, request: _PendingGenerationRequest):
        """
        The exact worker/thread construction _start_generation() always
        performed directly, before Mission 115 — unchanged in substance,
        now reading every value from an already-captured
        _PendingGenerationRequest instead of local variables, so it
        behaves identically whether called immediately (Forge, or
        ComfyUI already RUNNING_OWNED/EXTERNAL_ACTIVE) or after a
        ComfyUI Local Start this page itself requested has completed.

        Mission 116: the single choke point both entry paths (immediate,
        or resolved-pending) funnel through — clearing
        comfyui_status_label here, rather than separately at each call
        site, guarantees the transient status text disappears exactly
        when the real generation departs, regardless of which path led
        here (including Forge, where it was always already empty).
        """
        self.comfyui_status_label.clear()
        self.generate_button.setEnabled(False)
        self._set_generation_controls_enabled(False)
        self._set_validation_buttons_enabled(False)

        thread = QThread()
        worker = GenerationWorker(
            self._generation_manager,
            request.prompt_text,
            request.output_directory,
            request.reference_images,
            request.reference_strength,
            width=request.width,
            height=request.height,
            steps=request.steps,
            cfg=request.cfg,
            sampler_name=request.sampler_name,
            scheduler=request.scheduler,
            seed=request.seed,
            negative_prompt=request.negative_prompt,
            lora_name=request.lora_name,
            lora_strength=request.lora_strength,
            engine=request.target_engine,
            checkpoint_name=request.checkpoint_name,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        # worker/thread are captured by value here (not re-read from
        # self._worker/self._thread when this fires, which may be much
        # later) — this is what makes it impossible for this cycle's
        # deferred cleanup to ever act on a newer cycle's objects, even
        # if the user starts a second generation (via Regenerate) before
        # this callback runs (see _cleanup_thread's docstring). Mission
        # 014 does not touch this mechanism.
        thread.finished.connect(lambda: self._cleanup_thread(worker, thread))

        self._thread = thread
        self._worker = worker

        thread.start()

    def _on_generation_finished(self, path):

        if not self._workspace_context_matches(self._generation_workspace_root):
            # The active workspace changed while this generation was
            # in flight (no cancellation exists — Mission 013's
            # accepted limitation, not revisited here). The file was
            # still written correctly into its origin workspace's
            # outputs/ folder (output_directory was fixed at
            # _start_generation() time), but it must never surface as
            # a pending result the user could Accept into whatever
            # workspace is current now — discard it silently instead.
            self._delete_pending_file(path)
            self._generation_workspace_root = None
            self.generate_button.setEnabled(True)
            self._set_generation_controls_enabled(True)
            return

        # Mission 014: the generated file is not registered into
        # Workspace.images here anymore — it becomes the pending result
        # awaiting Accept/Reject/Regenerate. generate_button stays
        # disabled: Accept/Reject/Regenerate is the only way forward
        # from here, avoiding two concurrent paths to start a new
        # generation.
        self._set_pending(path)

    def _on_generation_failed(self, message):

        self._generation_workspace_root = None
        self.generate_button.setEnabled(True)
        self._set_generation_controls_enabled(True)
        self._set_validation_buttons_enabled(False)

        QMessageBox.critical(
            self,
            "Erreur de génération",
            message
        )

    def _on_accept_clicked(self):

        if self._pending_path is None:
            return

        self._accept_pending_result()

    def _accept_pending_result(self) -> bool:
        """
        Mission 084: the single accept-and-persist primitive shared by
        _on_accept_clicked() (button, self._pending_path already
        confirmed non-None by the caller) and
        confirm_pending_result_change() (guard, same precondition).

        Returns True only on genuine success (image added to
        Workspace.images, pending fully cleared). Returns False on any
        of the 3 existing failure paths, each of which already shows
        its own QMessageBox and decides for itself whether
        self._pending_path survives: a real WorkspaceManagerError
        preserves it (retry possible — see Mission 067 rationale
        below); a stale workspace context or a vanished file both
        already clear it unconditionally, since neither leaves
        anything left to retry.
        """
        # Defense in depth: reset_for_workspace_change() (subscribed by
        # MainWindow to WORKSPACE_CREATED/OPENED/CLOSED/RENAMED) already
        # invalidates a pending result the moment the workspace context
        # changes — this guard only protects against Accept somehow
        # being reached before that event was delivered/processed.
        # Mission 084: also structurally unreachable when called from
        # confirm_pending_result_change() itself, since that guard
        # always runs before any transition has actually mutated
        # current_workspace — kept as-is for the button's own direct
        # click and as defense in depth.
        if not self._workspace_context_matches(self._generation_workspace_root):
            QMessageBox.warning(
                self,
                "Projet changé",
                "Le projet actif a changé depuis cette génération ; le résultat n'a pas été enregistré."
            )
            self._clear_pending(delete_file=True)
            self.generate_button.setEnabled(True)
            self._set_generation_controls_enabled(True)
            return False

        if not Path(self._pending_path).exists():
            QMessageBox.warning(
                self,
                "Fichier introuvable",
                "Le fichier généré n'existe plus sur le disque ; impossible de l'enregistrer."
            )
            self._clear_pending(delete_file=False)
            self.generate_button.setEnabled(True)
            self._set_generation_controls_enabled(True)
            return False

        # WorkspaceManager.add_images() runs here, on the Qt main
        # thread — never from the worker itself, since
        # Workspace/WorkspaceManager are plain Python objects with no
        # thread-safety guarantee (Mission 013 architecture decision,
        # unchanged by Mission 014).
        #
        # Mission 067: add_images() now rollbacks Workspace.images and
        # compensates the passthrough-or-copy distinction itself before
        # re-raising on a save() failure — the pending image was never
        # actually added, so nothing here is cleared and no control is
        # re-enabled: the page stays in exactly the same pre-Accept
        # state (pending image still visible, Accepter/Rejeter/
        # Régénérer still available), and a second "Accepter" is a
        # genuine new attempt rather than a silent no-op.
        try:
            self._workspace_manager.add_images([self._pending_path])
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer l'image générée dans le projet : {exc}\n"
                "Le résultat reste en attente — vous pouvez réessayer Accepter ou Rejeter."
            )
            return False

        self._clear_pending(delete_file=False)
        self.generate_button.setEnabled(True)
        self._set_generation_controls_enabled(True)
        return True

    def _on_reject_clicked(self):

        if self._pending_path is None:
            return

        self._reject_pending_result()

    def _reject_pending_result(self) -> None:
        """
        Mission 084: the single reject-and-discard primitive shared by
        _on_reject_clicked() (button) and confirm_pending_result_change()
        (guard). A physical cleanup failure is only ever a best-effort
        warning here — it never blocks anything, on the button or from
        the guard: the pending result is discarded from the page's own
        tracking either way (see _clear_pending()'s own contract).
        """
        deleted = self._clear_pending(delete_file=True)
        self.generate_button.setEnabled(True)
        self._set_generation_controls_enabled(True)

        if not deleted:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Le fichier temporaire n'a pas pu être supprimé du disque ; "
                "il ne sera pas enregistré, mais peut rester présent sur le disque."
            )

    def _on_regenerate_clicked(self):

        if self._pending_path is None:
            return

        # Mission 096: validated before the still-pending previous
        # result is discarded below — an invalid width/height/seed must
        # never destroy a result the architect could otherwise still
        # Accept/Reject (see _validate_generation_parameters()'s own
        # docstring).
        if not self._validate_generation_parameters():
            return

        prompt_text = self.prompt.toPlainText()

        deleted = self._clear_pending(delete_file=True)

        if not deleted:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "L'ancien résultat temporaire n'a pas pu être supprimé du disque ; "
                "une nouvelle génération va tout de même être lancée."
            )

        self._start_generation(prompt_text)

    def _on_enlarge_clicked(self):
        # Mission 015: strictly a passive viewer over the pending file
        # already on disk — ImagePreviewDialog receives only a str
        # (self._pending_path), never a reference to this page or to
        # WorkspaceManager, so it has no way to affect the pending
        # state, Accept/Reject/Regenerate, or Workspace.images. It is
        # also modal (exec()), so no other button here can be clicked
        # while it is open.
        if self._pending_path is None:
            return

        ImagePreviewDialog(self._pending_path, parent=self).exec()

    def _on_select_reference_clicked(self):
        # Mission 022: same file-picker pattern already used by
        # ImagesPage.import_images()/DatasetsPage.import_images() —
        # single-file selection (getOpenFileName, not the plural
        # getOpenFileNames), since this page's UI only ever holds 0 or
        # 1 reference. No existence/business validation is done here:
        # a file removed between selection and Generate is naturally
        # caught as a GenerationError when upload_image() runs.
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner une image de référence",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not file_path:
            return

        self._apply_selected_reference(file_path)

    def _on_select_reference_from_gallery_clicked(self):
        # Mission 086: second source for the exact same single
        # reference primitive — no copy is ever made here or later:
        # GenerationManager.generate()/ComfyUIEngine.upload_image()
        # only ever read self._reference_image_path, regardless of
        # whether it came from this dialog or from QFileDialog above.
        if not self._workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de choisir une image de référence."
            )
            return

        image_paths = [
            image.file_path for image in self._workspace_manager.current_workspace.images
        ]

        if not image_paths:
            QMessageBox.information(
                self,
                "Galerie Images vide",
                "Aucune image dans la galerie Images."
            )
            return

        dialog = SelectImagesDialog(
            image_paths,
            parent=self,
            selection_mode=QListWidget.SingleSelection,
            title="Choisir une image de référence",
            info_text="Sélectionnez une image de la galerie à utiliser comme référence :",
        )
        if dialog.exec() != QDialog.Accepted:
            return

        selected_paths = dialog.selected_paths()
        if not selected_paths:
            return

        self._apply_selected_reference(selected_paths[0])

    def _apply_selected_reference(self, file_path):
        self._reference_image_path = file_path
        self.reference_label.setText(f"{Path(file_path).name} — Pose / composition")
        self.remove_reference_button.setEnabled(True)
        self.reference_strength_slider.setEnabled(True)
        # Mission 096: width/height stop applying the moment a reference
        # becomes active — build_img2img_workflow() derives the latent's
        # dimensions from the reference image itself (see
        # MISSION_096.md section 3/10). Values are left untouched (not
        # reset), so they are immediately usable again unchanged if the
        # reference is removed.
        self.width_spinbox.setEnabled(False)
        self.height_spinbox.setEnabled(False)

    def _on_remove_reference_clicked(self):
        self._clear_reference_selection()

    def _clear_reference_selection(self):
        self._reference_image_path = None
        self.reference_label.setText("Aucune référence sélectionnée")
        self.remove_reference_button.setEnabled(False)
        self.reference_strength_slider.setEnabled(False)
        self.reference_strength_slider.setValue(DEFAULT_REFERENCE_STRENGTH_PERCENT)
        # Mission 096: width/height apply again now that the txt2img
        # path is back in effect.
        self.width_spinbox.setEnabled(True)
        self.height_spinbox.setEnabled(True)

    def _on_reference_strength_changed(self, value):
        self.reference_strength_value_label.setText(self._format_reference_strength(value))

    @staticmethod
    def _format_reference_strength(value):
        return f"{value / 100:.2f}"

    def _on_random_seed_toggled(self, checked):
        # Mission 096: seed_edit only ever matters in fixed mode — kept
        # visible but disabled otherwise (same discoverability/stable-
        # layout treatment as remove_reference_button/
        # reference_strength_slider above), never cleared: the
        # architect's last-typed value survives toggling back and forth.
        self.seed_edit.setEnabled(not checked)

    def _on_refresh_sampler_scheduler_clicked(self):
        """
        Mission 096, extended by Mission 108: on-demand discovery of
        checkpoint/sampler_name/scheduler for whichever engine is
        currently active (self._active_engine()) — same graceful-
        fallback UX as SettingsPage.refresh_checkpoints()/refresh_loras()
        (short discovery-specific timeout, a clear status message on
        failure, manual typing in the editable combo boxes always
        remains available regardless of outcome). Never blocks on this
        instance's own generation-appropriate timeout (120.0s default)
        — see MISSION_096.md section 6.

        Mission 108: this is the single "Rafraîchir" button covering
        all three capabilities — deliberately not split into two
        buttons, and deliberately not triggered automatically on engine
        change (MISSION_108.md section 3.7: the current discovery calls
        are synchronous and would otherwise freeze the UI for up to
        SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT seconds against an
        unreachable engine). All three discovery calls target the exact
        same engine object — a failure on the first (checkpoints) never
        touches any combo, so no partial/inconsistent state across the
        three lists is ever displayed.
        """
        target_engine = self._active_engine()

        try:
            checkpoints = self._generation_manager.list_checkpoints(
                engine=target_engine, timeout=SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT
            )
            samplers = self._generation_manager.list_samplers(
                engine=target_engine, timeout=SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT
            )
            schedulers = self._generation_manager.list_schedulers(
                engine=target_engine, timeout=SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT
            )
        except GenerationError:
            self.sampler_scheduler_status_label.setText(
                "Découverte impossible : moteur injoignable ou configuration invalide. "
                "La saisie manuelle du checkpoint/sampler/scheduler reste disponible."
            )
            return

        current_checkpoint = self.checkpoint_combo.currentText()
        current_sampler = self.sampler_combo.currentText()
        current_scheduler = self.scheduler_combo.currentText()

        # blockSignals: repopulating a QComboBox fires
        # currentIndexChanged/editTextChanged transiently for every
        # intermediate state (clear(), each addItem()) — same rationale
        # as SettingsPage.refresh_checkpoints()/refresh_loras().
        self.checkpoint_combo.blockSignals(True)
        self.checkpoint_combo.clear()
        self.checkpoint_combo.addItems(checkpoints)
        self.checkpoint_combo.setCurrentText(current_checkpoint)
        self.checkpoint_combo.blockSignals(False)

        self.sampler_combo.blockSignals(True)
        self.sampler_combo.clear()
        self.sampler_combo.addItems(samplers)
        self.sampler_combo.setCurrentText(current_sampler)
        self.sampler_combo.blockSignals(False)

        self.scheduler_combo.blockSignals(True)
        self.scheduler_combo.clear()
        self.scheduler_combo.addItems(schedulers)
        self.scheduler_combo.setCurrentText(current_scheduler)
        self.scheduler_combo.blockSignals(False)

        self.sampler_scheduler_status_label.setText(
            f"{len(checkpoints)} checkpoint(s), {len(samplers)} sampler(s), "
            f"{len(schedulers)} scheduler(s) découverts."
        )

    def _on_engine_changed(self, index: int):
        """
        Mission 108: guards, in order — a generation genuinely in
        progress or an unresolved pending result both block the switch
        outright, reusing the exact guards already established for
        Workspace/application-close transitions (Missions 084/085),
        never a new/duplicated mechanism. A blocked switch reverts
        engine_combo back to its last confirmed index (index was already
        applied by Qt by the time this signal fires — see
        _revert_engine_combo_selection()). A confirmed switch
        invalidates checkpoint/sampler/scheduler immediately (section
        3.7) — never leaves a ComfyUI-discovered value looking like a
        valid Forge selection, or vice versa.
        """
        if index == self._engine_combo_confirmed_index:
            return

        if not self.confirm_no_active_generation(
            "Terminez ou attendez la fin de la génération en cours avant de "
            "changer de moteur."
        ):
            self._revert_engine_combo_selection()
            return

        if not self.confirm_pending_result_change():
            self._revert_engine_combo_selection()
            return

        self._engine_combo_confirmed_index = index
        self._invalidate_capabilities()

    def _revert_engine_combo_selection(self):
        self.engine_combo.blockSignals(True)
        self.engine_combo.setCurrentIndex(self._engine_combo_confirmed_index)
        self.engine_combo.blockSignals(False)

    def _invalidate_capabilities(self):
        """
        Mission 108, section 3.7: immediately empties
        checkpoint/sampler/scheduler on an engine switch — no automatic
        rediscovery (would risk a perceptible synchronous freeze against
        an unreachable engine), no ComfyUI-flavored default silently
        left in place under a Forge selection (or vice versa). The
        architect must click "Rafraîchir" to populate them again for
        the newly active engine.
        """
        self.checkpoint_combo.blockSignals(True)
        self.checkpoint_combo.clear()
        self.checkpoint_combo.blockSignals(False)

        self.sampler_combo.blockSignals(True)
        self.sampler_combo.clear()
        self.sampler_combo.blockSignals(False)

        self.scheduler_combo.blockSignals(True)
        self.scheduler_combo.clear()
        self.scheduler_combo.blockSignals(False)

        self.sampler_scheduler_status_label.setText(
            "Changement de moteur — cliquez sur Rafraîchir pour découvrir le "
            "checkpoint/sampler/scheduler de ce moteur."
        )

    def _set_generation_controls_enabled(self, enabled):
        # Mission 096: renamed from _set_reference_controls_enabled —
        # this method now covers every control a generation in progress
        # must freeze, not only the reference-selection ones.
        self.select_reference_button.setEnabled(enabled)
        self.select_reference_from_gallery_button.setEnabled(enabled)
        self.remove_reference_button.setEnabled(enabled and self._reference_image_path is not None)
        self.reference_strength_slider.setEnabled(enabled and self._reference_image_path is not None)

        # Mission 096: width/height are only ever meaningful on the
        # txt2img path (no reference active) — same "enabled and
        # reference state" conditional as remove_reference_button/
        # reference_strength_slider above, but the opposite direction
        # (enabled only when NO reference is active, not when one is;
        # see also _apply_selected_reference()/_clear_reference_selection()
        # below, which apply this same condition outside of a
        # generation cycle).
        self.width_spinbox.setEnabled(enabled and self._reference_image_path is None)
        self.height_spinbox.setEnabled(enabled and self._reference_image_path is None)

        # Mission 096: the remaining generation-parameter controls apply
        # identically on both the txt2img and img2img paths — simply
        # disabled while a generation is in progress, like
        # generate_button itself, re-enabled afterward regardless of
        # reference state. seed_edit additionally depends on the seed
        # mode itself, same pattern as remove_reference_button depending
        # on reference state above.
        self.steps_spinbox.setEnabled(enabled)
        self.cfg_spinbox.setEnabled(enabled)
        self.sampler_combo.setEnabled(enabled)
        self.scheduler_combo.setEnabled(enabled)
        self.refresh_sampler_scheduler_button.setEnabled(enabled)
        self.negative_prompt_edit.setEnabled(enabled)
        self.random_seed_checkbox.setEnabled(enabled)
        self.seed_edit.setEnabled(enabled and not self.random_seed_checkbox.isChecked())

        # Mission 108: the engine selector and checkpoint combo freeze
        # like every other generation-parameter control above — a
        # generation already in flight targets a specific engine/
        # checkpoint captured at _start_generation() time; changing
        # either mid-flight must never appear possible from the UI
        # (confirm_no_active_generation() is a second, independent
        # guard for the same invariant — see _on_engine_changed()).
        self.engine_combo.setEnabled(enabled)
        self.checkpoint_combo.setEnabled(enabled)

    def prompt_text(self) -> str:
        return self.prompt.toPlainText()

    def set_prompt_text(self, text: str) -> None:
        # Mission 033: the intentional public write side of the pair
        # above — lets MainWindow deposit a prompt received from
        # PromptsPage without reaching into self.prompt (a QTextEdit)
        # directly.
        #
        # Mission 083: a programmatic load of a working copy, not new
        # user work — the source text remains protected at its origin
        # (already a persisted Prompt, or still guarded by PromptsPage's
        # own dirty-state if not). blockSignals() prevents
        # _on_prompt_text_changed() from marking this dirty; _dirty and
        # save_prompt_button are resynchronized explicitly instead,
        # exactly as reset_for_context_change() does below. Any further
        # edit made in Inference itself marks it dirty normally.
        self.prompt.blockSignals(True)
        self.prompt.setPlainText(text)
        self.prompt.blockSignals(False)

        self._dirty = False
        self.save_prompt_button.setEnabled(bool(text.strip()))

    def reset_for_workspace_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED/
        RENAMED (never WORKSPACE_SAVED — saving does not change which
        workspace is current, e.g. Accept's own add_images()->save()
        must not invalidate the pending result it is in the middle of
        clearing). Each of those four events means WorkspaceManager.
        current_workspace has just been replaced, cleared, or had its
        root path changed (Mission 027's WORKSPACE_RENAMED) — a pending
        result computed for the previous workspace/root must never be
        offered to the new one. An in-flight generation (no pending
        yet) is deliberately left running — no cancellation exists; its
        result is discarded when it eventually arrives, in
        _on_generation_finished()'s own workspace check above.

        Mission 084: confirm_pending_result_change() below now protects
        this exact destruction with an explicit Accept/Reject/Cancel
        choice, called by MainWindow before every transition that would
        otherwise reach this handler through one of the 4 events above.
        By the time any of those events actually fires, self._pending_path
        is therefore already None in the normal flow (that guard clears
        it itself, via Accept or Reject, before the transition it
        guards is ever allowed to proceed) — the destruction below is
        kept unmodified as a pure safety net for any state this guard
        does not cover (there is none in the normal flow), never a
        second, competing decision point.
        """
        if self._pending_path is not None:
            self._clear_pending(delete_file=True)
            self.generate_button.setEnabled(True)
            self._set_generation_controls_enabled(True)

        # Mission 115: a generation still waiting on ComfyUI Local's
        # Start belongs exclusively to the workspace context it was
        # snapshotted under — never silently carried over into whichever
        # workspace is now current. Unlike an in-flight generation
        # thread (deliberately left running above, see this method's own
        # docstring), nothing has actually been requested from
        # GenerationManager/ComfyUI yet at this point, so there is
        # nothing irreversible to let finish: it is safe, and required,
        # to invalidate it outright and restore the UI immediately. A
        # comfyui_lifecycle_manager Start already in flight for it is
        # left running (it may still be useful to a later generation);
        # comfyui_lifecycle_manager.stop() is deliberately not called
        # here — Toolkit-level ownership of that Start is independent of
        # any one Page's interest in its outcome.
        if self._pending_generation_request is not None:
            self._pending_generation_request = None
            self._generation_workspace_root = None
            self.comfyui_status_label.clear()
            self.generate_button.setEnabled(True)
            self._set_generation_controls_enabled(True)

        # Mission 022: the selected reference is transitory and never
        # tied to Workspace.images/project.json — reset here for the
        # same reason a pending result is invalidated above: it must
        # never silently carry over into whichever workspace is now
        # current.
        self._clear_reference_selection()

    def confirm_context_change(self) -> bool:
        """
        Mission 083: same public contract as PromptsPage/CharactersPage/
        LoRAPage/SettingsPage's own confirm_context_change() — called by
        MainWindow before a Workspace switch (new_project()/
        open_project()) or application close, in each case before any
        irreversible step. Returns True if the caller may proceed, False
        if the transition must be abandoned entirely. If not dirty,
        returns True immediately with no dialog at all.

        Save recreates "Enregistrer dans Prompts"'s exact existing
        contract (always a new Prompt, name entered through the same
        QInputDialog) rather than silently generating a name — cancelling
        that name dialog, an empty/invalid name, no principal Character/
        Workspace, or a persistence failure all abandon the whole
        transition (False), leaving self.prompt and self._dirty
        untouched, exactly like a Cancel choice below.
        """
        if not self._dirty:
            return True

        text = self.prompt.toPlainText()

        if not text.strip():
            # Mirrors _on_save_prompt_clicked()'s own empty-text no-op:
            # nothing a Save could meaningfully persist, so there is
            # nothing left to protect either.
            self._dirty = False
            return True

        choice = self._confirm_discard_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            name, ok = QInputDialog.getText(self, "Nouveau prompt", "Nom :")

            if not ok or not name.strip():
                return False

            if not self._save_prompt_as_new(name.strip(), text):
                return False

            self._dirty = False

        return True

    def _confirm_discard_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Le prompt actuel contient des modifications non enregistrées. "
            "Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def reset_for_context_change(self, _payload=None):
        """
        Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED only
        — never WORKSPACE_RENAMED, unlike reset_for_workspace_change()
        above, which stays exclusively responsible for _pending_path/the
        reference selection and keeps its own unrelated 4-event
        subscription unchanged. A rename does not invalidate the
        prompt's own root-independent content, so self.prompt/self._dirty
        must survive it intact — exactly like PromptsPage/CharactersPage/
        LoRAPage/SettingsPage's own reset_for_context_change(), which is
        likewise never subscribed to WORKSPACE_RENAMED.
        """
        self.prompt.blockSignals(True)
        self.prompt.setPlainText("")
        self.prompt.blockSignals(False)

        self._dirty = False
        self.save_prompt_button.setEnabled(False)

    def confirm_pending_result_change(self) -> bool:
        """
        Mission 084: same True=proceed/False=abandon public contract as
        confirm_context_change() above, but deliberately a separate
        method over an entirely independent draft — self._pending_path
        (a future Workspace.images entry) rather than self.prompt/
        self._dirty (a future Prompt). Never merged into
        confirm_context_change(): the two states are unrelated, and
        keeping them as two sequential, independently testable guards
        avoids any ambiguity about internal ordering within one method.
        Called by MainWindow as the 6th and last guard in each of its 3
        chains (new_project()/open_project()/closeEvent()), and as the
        sole guard in rename_project() (see reset_for_workspace_change()
        docstring — a rename never destroys a dirty prompt, only a
        pending result). If there is no pending result, returns True
        immediately with no dialog at all.
        """
        if self._pending_path is None:
            return True

        choice = self._confirm_pending_before_switch()

        if choice == "cancel":
            return False

        if choice == "accept":
            if self._accept_pending_result():
                return True
            # _accept_pending_result() already showed the appropriate
            # QMessageBox for whichever of its 3 failure paths fired.
            # A real persistence failure (WorkspaceManagerError)
            # preserves self._pending_path — a genuine retry is still
            # possible, so the transition must be refused, exactly like
            # Cancel. A stale workspace context or a vanished file both
            # already cleared self._pending_path themselves — there is
            # no longer any recoverable result to protect, so refusing
            # the transition would serve no purpose; let it proceed.
            return self._pending_path is None

        self._reject_pending_result()  # choice == "reject"
        return True

    def _confirm_pending_before_switch(self) -> str:
        box = QMessageBox(self)
        box.setWindowTitle("Génération en attente")
        box.setText(
            "Une image générée n'a pas encore été acceptée ou rejetée. "
            "Que souhaitez-vous faire avant de continuer ?"
        )
        accept_button = box.addButton("Accepter l'image", QMessageBox.AcceptRole)
        reject_button = box.addButton("Rejeter l'image", QMessageBox.DestructiveRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is accept_button:
            return "accept"
        if clicked is reject_button:
            return "reject"
        return "cancel"

    def is_generation_active(self) -> bool:
        """
        Mission 085: the one reliable "a generation is genuinely still
        producing work" signal, deliberately encapsulated here rather
        than left to MainWindow to inspect self._thread directly.

        self._thread is not None is NOT sufficient on its own — the
        mini-audit demonstrated a real, empirically confirmed window
        where the worker thread has already finished (QThread.wait()
        has returned) but the cross-thread queued signals
        (worker.finished -> _on_generation_finished, thread.finished ->
        _cleanup_thread) have not been delivered yet: self._thread is
        still not None and self._pending_path is still None in that
        window, even though nothing is actually running anymore.
        QThread.isRunning() reflects the real OS thread state
        independently of that deferred delivery, so combining both
        conditions never blocks a transition on a thread that has
        already finished its work.

        Mission 115: a generation waiting on ComfyUI Local's Start
        (self._pending_generation_request is not None) has not created
        self._thread yet, but is just as genuinely "in flight" from the
        architect's point of view — confirm_no_active_generation() must
        refuse a close/rename during this window exactly as it already
        does for a running worker thread, otherwise the pending request
        could be silently orphaned by a navigation/close guard that
        believes nothing is happening.
        """
        return (
            (self._thread is not None and self._thread.isRunning())
            or self._pending_generation_request is not None
        )

    def confirm_no_active_generation(self, blocked_message: str) -> bool:
        """
        Mission 085: True=proceed/False=abandon, same contract shape as
        confirm_context_change()/confirm_pending_result_change() above,
        but deliberately never merged with either — a still-running
        generation has not produced any result yet (no dirty prompt
        text, no pending image), so there is nothing for those two
        guards to meaningfully protect; asking Accept/Reject/Cancel at
        this point would be nonsensical (see
        confirm_pending_result_change()'s own docstring: no cancellation
        mechanism exists for the worker itself — Mission 013's accepted
        limitation, not revisited here). Never blocks waiting for the
        worker: if a generation is genuinely active, the transition is
        refused immediately and the caller must not proceed with any
        further guard or any Workspace mutation. Once the generation
        finishes on its own, _on_generation_finished() runs normally and
        the result becomes a pending result, protected on the next
        attempt by confirm_pending_result_change() exactly as before.

        blocked_message is caller-supplied (MainWindow) so the same
        underlying check serves both closeEvent() and rename_project()
        with their own wording, without turning this into a shared
        cross-Page abstraction — the check and the dialog stay local to
        InferencePage, only the message text varies by caller.
        """
        if not self.is_generation_active():
            return True

        QMessageBox.warning(self, "Génération en cours", blocked_message)
        return False

    def _workspace_context_matches(self, expected_root):
        return (
            expected_root is not None
            and self._workspace_manager.opened
            and str(self._workspace_manager.current_workspace.root) == expected_root
        )

    def _set_pending(self, path):

        self._pending_path = path

        pixmap = QPixmap(path)
        self._pending_pixmap = pixmap if not pixmap.isNull() else None
        self._update_preview()

        self._set_validation_buttons_enabled(True)

    def _clear_pending(self, delete_file):
        """
        Returns True if there was nothing to delete or deletion
        succeeded, False if delete_file was requested and the file
        could not be removed (caller decides whether/how to surface
        that to the user).
        """
        path = self._pending_path

        self._pending_path = None
        self._pending_pixmap = None
        self._generation_workspace_root = None
        self.preview_label.clear()
        self._set_validation_buttons_enabled(False)

        if delete_file and path is not None:
            return self._delete_pending_file(path)

        return True

    @staticmethod
    def _delete_pending_file(path):
        # A pending result is never persisted, so a file already
        # missing (e.g. removed manually) or undeletable (e.g.
        # permission error) must never crash the UI — it is simply no
        # longer tracked as pending either way. A file that is already
        # gone counts as success (the desired end state — "no file left
        # behind" — already holds; nothing to warn the user about).
        # Only a genuine deletion failure (still present, still on
        # disk) is reported back to the caller as such.
        try:
            Path(path).unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _set_validation_buttons_enabled(self, enabled):
        self.accept_button.setEnabled(enabled)
        self.reject_button.setEnabled(enabled)
        self.regenerate_button.setEnabled(enabled)
        self.preview_enlarge_button.setEnabled(enabled)

    def _update_preview(self):

        if self._pending_pixmap is None:
            self.preview_label.clear()
            return

        scaled = self._pending_pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview()

    def _cleanup_thread(self, worker, thread):
        """
        Runs once this specific cycle's thread has fully stopped
        (thread.finished). worker/thread are the exact objects created
        for this cycle, captured by value at connect() time in
        _start_generation() — never read from self._worker/
        self._thread here, so a second generation the user already
        started (whose objects now live in self._worker/self._thread)
        can never be torn down by this, older, callback.

        self._worker/self._thread are only reset to None if they still
        point at *this* cycle's objects — if a newer cycle has already
        replaced them, those newer references are left untouched.
        """
        worker.deleteLater()
        thread.deleteLater()

        if self._worker is worker:
            self._worker = None

        if self._thread is thread:
            self._thread = None

    def shutdown(self):
        """
        Called from MainWindow.closeEvent() so a generation in progress
        never leaves a dangling thread behind when the application
        closes (Mission 013 — minimal handling, no cancellation), and
        so a pending, not-yet-accepted result never survives as an
        orphan file nor gets silently persisted (Mission 014).

        Mission 115: also drops a generation still waiting on ComfyUI
        Local's Start, if one somehow still exists here — in the normal
        flow, is_generation_active()/confirm_no_active_generation()
        already refuse the close while one is pending, so closeEvent()
        never reaches shutdown() in that case; this is a defensive net
        for any other real caller of shutdown(), never a second decision
        point. comfyui_lifecycle_manager's own Start/Stop lifecycle is
        untouched here — MainWindow's own confirm_safe_to_close() guard
        is exclusively responsible for it.
        """
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()

        self._pending_generation_request = None
        self.comfyui_status_label.clear()
        self._clear_pending(delete_file=True)
