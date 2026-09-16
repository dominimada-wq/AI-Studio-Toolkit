from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QSpinBox,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QPlainTextEdit,
    QToolButton,
    QScrollArea,
)

from src.engines.onetrainer_config import OneTrainerConfigError
from src.engines.onetrainer_launch import OneTrainerLaunchError, resolve_onetrainer_launch
from src.managers.lora_library_manager import LoRALibraryError
from src.managers.training_manager import (
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
    TRAINING_ARCHITECTURE_FLUX,
    TRAINING_ARCHITECTURES,
    TRAINING_JOB_STATE_RUNNING,
    TRAINING_JOB_STATE_SUCCEEDED,
    TrainingJobError,
    TrainingPreparationError,
)
from src.managers.workspace_manager import WorkspaceManagerError
from src.ui.training_job_runner import TrainingJobRunner
from src.utils.lora_library_path import LoRALibraryPathError, resolve_lora_library_root

# Mission 097 section 3.7: architecture-appropriate resolution
# suggestions — confirmed against OneTrainer's own real shipped LoRA
# presets ("#sd 1.5 LoRA.json"/"#sdxl 1.0 LoRA.json"/"#flux LoRA.json"),
# applied to resolution_spinbox the moment an architecture is chosen
# (never stored as a Training default — see Training.resolution's own
# docstring). A value the architect then changes manually is never
# overwritten again by this same suggestion.
_SUGGESTED_RESOLUTION_BY_ARCHITECTURE = {
    TRAINING_ARCHITECTURE_SD15: 512,
    TRAINING_ARCHITECTURE_SDXL: 1024,
    TRAINING_ARCHITECTURE_FLUX: 768,
}

# Mission 121 section 3.2: the UI-proposed vocabulary is deliberately
# narrower than the 13 real DataType values OneTrainer accepts (see
# MISSION_121.md section 3.2, level 3) — restricted to the 4 non-
# quantized values confirmed loadable by the SD1.5/SDXL/Flux
# modelLoaders actually audited. Identical for all three architectures,
# including Flux: an official Flux preset using a quantized value
# (NFLOAT_4/FLOAT_8/INT_W8A8) is never presented here as proof of
# compatibility with this machine's Quadro P4000/Pascal/sm_61.
#
# Mission 126 section 2.1/3.1: NFLOAT_4 joins this shared list, on the
# same generic mechanism, deliberately with no new per-architecture or
# per-component restriction — a real-code audit of OneTrainer's own
# quantize_layers()/replace_linear_with_quantized_layers() confirmed
# NFLOAT_4 is technically supported uniformly by every weight_dtype
# component on every architecture Toolkit exposes (SD1.5/SDXL/FLUX),
# never restricted to the transformer/text_encoder_2 pair the FLUX
# official preset happens to use — that preset choice is never turned
# into a Toolkit-side validation rule (MISSION_126.md section 3.1). Its
# real VRAM/Pascal-sm_61 behavior remains unmeasured on this machine
# (see MISSION_126.md section 3.4) — this UI change exposes the
# capability, it does not claim to have validated it experimentally.
_DTYPE_UI_CHOICES = ("FLOAT_16", "FLOAT_32", "BFLOAT_16", "TFLOAT_32", "NFLOAT_4")

# Mission 126 section 2.5: deliberately narrower than
# TimestepDistribution's 7 real OneTrainer enum values — restricted to
# the one value FLUX's official LoRA preset actually configures
# (LOGIT_NORMAL) plus the engine's own default (UNIFORM), for
# transparency. This is a UI vocabulary choice only, never a claim that
# OneTrainer itself does not support SIGMOID/HEAVY_TAIL/COS_MAP/
# INVERTED_PARABOLA/BETA — the Domain field stays a plain str, capable
# of carrying any of the 7 real values (e.g. from a hand-edited
# project.json), and this tuple can grow in a future mission without
# any Domain/engine change.
_TIMESTEP_DISTRIBUTION_UI_CHOICES = ("UNIFORM", "LOGIT_NORMAL")


def _build_dtype_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("(non configuré)", "")
    for value in _DTYPE_UI_CHOICES:
        combo.addItem(value, value)
    return combo


# Mission 127 section 6: the 3 real values of OneTrainer's own
# GradientCheckpointingMethod enum, transmitted verbatim — never a
# Toolkit-facing translation (unlike lora_layer_filter's "ATTN_MLP").
# Generic to every architecture this project supports (see
# MISSION_127.md section 3.1) — never filtered by architecture, unlike
# the Flow-matching (FLUX) section of Mission 126.
_GRADIENT_CHECKPOINTING_UI_CHOICES = ("OFF", "ON", "CPU_OFFLOADED")


# Mission 127 section 7: the tooltip is a mandatory, factual contract
# term of this mission — CPU_OFFLOADED must never be presented as a
# universal VRAM improvement over ON. The real asymmetry (confirmed by
# direct reading of OneTrainer's own LayerOffloadConductor/checkpointing
# code, MISSION_127.md section 3.2/5): on SD1.5/SDXL, with OneTrainer's
# own default offloading settings (enable_activation_offloading=True,
# enable_async_offloading=True, layer_offload_fraction=0.0 — none of
# which this mission exposes), CPU_OFFLOADED behaves exactly like ON,
# because the UNet never gets an offloading conductor attached
# (offload_enabled=False, hardcoded in OneTrainer's own setup code) and
# its Text Encoder has no offloadable activation parameters registered.
# Only FLUX gets a real, additional benefit from CPU_OFFLOADED alone —
# activation offloading of its transformer blocks.
_GRADIENT_CHECKPOINTING_TOOLTIP = (
    "OFF : pas de gradient checkpointing (activations conservées telles quelles).\n"
    "ON : gradient checkpointing standard (recalcule les activations au lieu de "
    "les conserver — réduit la VRAM, augmente le temps d'entraînement).\n"
    "CPU_OFFLOADED : ajoute un déplacement des activations vers la RAM système, "
    "là où l'architecture OneTrainer le supporte. Avec les réglages d'offloading "
    "actuels du moteur, cela apporte un déplacement d'activations réel pour FLUX ; "
    "pour SD1.5/SDXL, le comportement reste identique à ON tant que le layer "
    "offloading n'est pas configuré séparément (non exposé par ce Toolkit)."
)


def _build_gradient_checkpointing_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("(non configuré)", "")
    for value in _GRADIENT_CHECKPOINTING_UI_CHOICES:
        combo.addItem(value, value)
    combo.setToolTip(_GRADIENT_CHECKPOINTING_TOOLTIP)
    return combo


# Mission 122 section 3.5: the UI-proposed vocabulary is deliberately
# narrower than the 43 real Optimizer values OneTrainer accepts —
# restricted to the 3 values backed directly by torch.optim, with no
# third-party optimizer dependency (bitsandbytes/prodigyopt/lion_pytorch/
# dadaptation/adv_optm/schedulefree/muon/pytorch_optimizer/timm — all
# confirmed installed in the real venv but never required by these three)
# and no 8-bit/quantized variant. Never presented as OneTrainer's
# complete optimizer vocabulary — the Domain (OneTrainerOptimizerSettings.
# optimizer: str) stays capable of storing any of the 43 real values
# (e.g. from a hand-edited project.json), same defensive tolerance as
# the dtype/learning_rate_scheduler vocabularies above.
_OPTIMIZER_UI_CHOICES = ("ADAM", "ADAMW", "SGD")


def _build_optimizer_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("(non configuré)", "")
    for value in _OPTIMIZER_UI_CHOICES:
        combo.addItem(value, value)
    return combo


# Mission 124: tri-state combo for text_encoder_train/text_encoder_2_train
# — a checkbox cannot represent "not configured" as a third state
# distinct from both True and False, hence a combo (same reasoning as
# every other "(non configuré)"-first combo on this page). "Entraîné"/
# "Gelé" match this page's existing French labeling conventions.
def _build_text_encoder_train_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Non configuré", None)
    combo.addItem("Entraîné", True)
    combo.addItem("Gelé", False)
    return combo


# Mission 126 section 2.5/8: "(non configuré)" first, same convention
# as every other dtype-style combo on this page — carries only
# _TIMESTEP_DISTRIBUTION_UI_CHOICES' restricted vocabulary, never a raw
# OneTrainer string beyond it.
def _build_timestep_distribution_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("(non configuré)", "")
    for value in _TIMESTEP_DISTRIBUTION_UI_CHOICES:
        combo.addItem(value, value)
    return combo


# Mission 126 section 2.6: same tri-state combo pattern as
# _build_text_encoder_train_combo() above, reused verbatim — "Activé"/
# "Désactivé" match this page's existing French labeling conventions
# for a boolean tri-state (distinct from "Entraîné"/"Gelé", which is
# specific to the Text Encoder train semantics).
def _build_dynamic_timestep_shifting_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Non configuré", None)
    combo.addItem("Activé", True)
    combo.addItem("Désactivé", False)
    return combo


# Mission 124 section 2.E/4.4: no OneTrainer-internal string ("attentions",
# "attn,ff.net") is ever exposed here — this combo carries only Toolkit's
# own functional discriminant ("ATTN_MLP"), translated to the real
# OneTrainer layer_filter/layer_filter_regex pair exclusively in
# src/engines/onetrainer_config.py.
def _build_lora_layer_filter_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("Non configuré", "")
    combo.addItem("Attention + MLP uniquement", "ATTN_MLP")
    return combo


class TrainingPage(QWidget):

    # Mission 109: local Presentation-layer signal, mirror of
    # PromptsPage.send_to_inference_requested (Mission 033) — carries
    # only the lora_id of a Job's already-imported LoRA, never a Domain
    # mutation. MainWindow is the sole subscriber/mediator; TrainingPage
    # never references InferencePage directly.
    use_lora_in_inference_requested = Signal(str)

    def __init__(
        self,
        training_manager,
        dataset_manager,
        workspace_manager,
        application_settings_manager,
        lora_library_manager,
    ):
        super().__init__()

        self.training_manager = training_manager
        self.dataset_manager = dataset_manager
        # Mission 036: source of authority for "no Workspace open" vs
        # "Workspace open without a principal Character" — see
        # create_training() below. Note: the "Aucun dataset disponible"
        # branch above it (list_datasets() empty) is a distinct,
        # out-of-scope ambiguity — see Mission 036 specification.
        self.workspace_manager = workspace_manager
        # Mission 100: the sole source of ApplicationSettings.onetrainer_path
        # — never ApplicationSettings.python_path (see
        # src/engines/onetrainer_launch.py's own docstring for why).
        self.application_settings_manager = application_settings_manager
        # Mission 103: same Central LoRA Library the Bibliothèque tab and
        # InferencePage already share — reused as-is, no new storage.
        self.lora_library_manager = lora_library_manager

        # Mission 100: runtime-only, never persisted — the runner/job
        # this Page is currently watching, at most one at a time (same
        # "single active operation" shape as GenerationManager._busy).
        # None whenever no Job started from this Page is in flight.
        self._active_runner = None
        self._active_job_id = None
        self._cancel_in_flight = False

        # Mission 105: dirty-draft protection for the 8 persistent
        # parameters below, same canonical pattern as CharactersPage/
        # LoRAPage/SettingsPage (Mission 078)/PromptsPage (Mission 038) —
        # a single flag for the whole form, never one per field.
        # _loaded_training_id distinguishes a non-destructive refresh
        # (active_training_id unchanged) from a genuine context change,
        # exactly like _loaded_lora_id/_loaded_prompt_id elsewhere.
        self._dirty = False
        self._loaded_training_id = None

        # Post-M121 correctif (hors périmètre M121 lui-même) : l'ajout de
        # la section "Advanced settings" a fait dépasser la hauteur totale
        # de TrainingPage au-delà d'une fenêtre normale, rendant le bas de
        # la page (dont la zone "Résultats des entraînements") physiquement
        # inatteignable — même symptôme et même solution que le mini-
        # correctif déjà appliqué à SettingsPage (hors périmètre Mission
        # 115) : le contenu existant, inchangé, est construit dans
        # content_widget puis placé dans un QScrollArea. `layout` référence
        # toujours exactement le même QVBoxLayout que tout le code
        # ci-dessous continue de peupler sans aucun changement.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        outer_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)

        title = QLabel("Training")
        title.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(title)

        training_buttons = QHBoxLayout()

        self.new_button = QPushButton("Nouvelle session")
        self.new_button.clicked.connect(self.create_training)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_training)

        training_buttons.addWidget(self.new_button)
        training_buttons.addWidget(self.delete_button)

        layout.addLayout(training_buttons)

        self.training_list = QListWidget()
        self.training_list.currentItemChanged.connect(self.on_training_selection_changed)

        layout.addWidget(self.training_list)

        # Mission 054: renaming is an immediate-commit edit, independent
        # of the Mission 051 alphabetical sort and of dataset_label
        # below — mirrors PromptsPage.name_edit.
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.rename_training)

        layout.addWidget(self.name_edit)

        self.dataset_label = QLabel("")

        layout.addWidget(self.dataset_label)

        # Mission 097: generic training hyperparameters — an explicit
        # "Enregistrer" commit, same pattern as LoRAPage.save_metadata()
        # (Mission 073's combined multi-field TrainingManager.update()),
        # never an immediate per-field commit like name_edit above.
        #
        # Mission 097 crash investigation (docs/missions/MISSION_097.md):
        # regrouped into a single QFormLayout (established pattern — see
        # LoRAPage.metadata_form) instead of one QHBoxLayout per field.
        # This is a structural simplification (same fields, same
        # behavior, fewer QLayout container objects) — it does not by
        # itself fix the native crash investigated in that mission; the
        # actual fix was to the test-only Qt dialog safety net.
        base_model_field = QHBoxLayout()

        self.base_model_edit = QLineEdit()
        self.base_model_edit.textChanged.connect(self._on_training_parameters_changed)
        self.base_model_browse_button = QPushButton("Parcourir un fichier…")
        self.base_model_browse_button.clicked.connect(self.browse_base_model_source)

        base_model_field.addWidget(self.base_model_edit)
        base_model_field.addWidget(self.base_model_browse_button)

        self.architecture_combo = QComboBox()
        self.architecture_combo.addItems(TRAINING_ARCHITECTURES)
        self.architecture_combo.setCurrentIndex(-1)
        # Mission 105: on_architecture_changed() itself now also marks
        # the form dirty (see its own body below) — a single connection,
        # never a second one to the same signal.
        self.architecture_combo.currentTextChanged.connect(self.on_architecture_changed)

        self.resolution_spinbox = QSpinBox()
        self.resolution_spinbox.setRange(64, 4096)
        self.resolution_spinbox.setSingleStep(64)
        self.resolution_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.epochs_spinbox = QSpinBox()
        self.epochs_spinbox.setRange(1, 10000)
        self.epochs_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.learning_rate_spinbox = QDoubleSpinBox()
        self.learning_rate_spinbox.setRange(0.0, 1.0)
        self.learning_rate_spinbox.setDecimals(6)
        self.learning_rate_spinbox.setSingleStep(0.0001)
        self.learning_rate_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.lora_rank_spinbox = QSpinBox()
        self.lora_rank_spinbox.setRange(1, 256)
        self.lora_rank_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.lora_alpha_spinbox = QDoubleSpinBox()
        self.lora_alpha_spinbox.setRange(0.0, 256.0)
        self.lora_alpha_spinbox.setDecimals(2)
        self.lora_alpha_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.trigger_word_edit = QLineEdit()
        self.trigger_word_edit.textChanged.connect(self._on_training_parameters_changed)

        # Mission 120: 0 displayed literally means "not configured" —
        # unlike resolution_spinbox above, there is no architecture-
        # suggested value to fall back to, so 0 stays a real, visible
        # choice in the spinbox itself (its range starts at 0, not 1).
        # Leaving it at 0 omits the key entirely from the built
        # OneTrainer config (see build_training_config()), exactly
        # reproducing today's behavior.
        self.batch_size_spinbox = QSpinBox()
        self.batch_size_spinbox.setRange(0, 4096)
        self.batch_size_spinbox.setSpecialValueText("(non configuré)")
        self.batch_size_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        self.gradient_accumulation_steps_spinbox = QSpinBox()
        self.gradient_accumulation_steps_spinbox.setRange(0, 4096)
        self.gradient_accumulation_steps_spinbox.setSpecialValueText("(non configuré)")
        self.gradient_accumulation_steps_spinbox.valueChanged.connect(
            self._on_training_parameters_changed
        )

        # Mission 120 section 4: vocabulary deliberately restricted to
        # OneTrainer's own LearningRateScheduler values this mission
        # actually supports — CUSTOM excluded (would need
        # custom_learning_rate_scheduler/scheduler_params, out of
        # scope). Empty string (blank first entry) means "not
        # configured" — never one of these real enum values.
        self.learning_rate_scheduler_combo = QComboBox()
        self.learning_rate_scheduler_combo.addItem("(non configuré)", "")
        self.learning_rate_scheduler_combo.addItem("Constant", "CONSTANT")
        self.learning_rate_scheduler_combo.addItem("Linear", "LINEAR")
        self.learning_rate_scheduler_combo.addItem("Cosine", "COSINE")
        self.learning_rate_scheduler_combo.addItem(
            "Cosine with restarts", "COSINE_WITH_RESTARTS"
        )
        self.learning_rate_scheduler_combo.addItem(
            "Cosine with hard restarts", "COSINE_WITH_HARD_RESTARTS"
        )
        self.learning_rate_scheduler_combo.addItem("REX", "REX")
        self.learning_rate_scheduler_combo.addItem("Adafactor", "ADAFACTOR")
        self.learning_rate_scheduler_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        # Mission 121: precision/weight-dtype fields — see
        # src/domain/onetrainer_settings.py's own docstring and
        # MISSION_121.md section 3 for the full architectural contract.
        # unet_weight_dtype/transformer_weight_dtype stay two distinct
        # Domain fields (never fused) even though only one combo is
        # ever shown at a time — _main_model_dtype_field tracks which
        # one main_model_weight_dtype_combo currently represents, and
        # each draft is explicitly reset to "" the moment it becomes
        # incompatible with the selected architecture (see
        # on_architecture_changed() below) — never silently carried
        # over nor resurfacing later in the same editing session.
        self._unet_weight_dtype_draft = ""
        self._transformer_weight_dtype_draft = ""
        self._main_model_dtype_field = "unet_weight_dtype"

        self.train_dtype_combo = _build_dtype_combo()
        self.train_dtype_combo.currentIndexChanged.connect(self._on_training_parameters_changed)

        # Mission 127: generic to every architecture — never reset or
        # hidden on architecture change (unlike the FLUX-only Flow-
        # matching combos of Mission 126), see on_architecture_changed()
        # below (this widget is deliberately absent from its reset/
        # visibility loop).
        self.gradient_checkpointing_combo = _build_gradient_checkpointing_combo()
        self.gradient_checkpointing_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        self.main_model_weight_dtype_combo = _build_dtype_combo()
        self.main_model_weight_dtype_combo.currentIndexChanged.connect(
            self._on_main_model_weight_dtype_changed
        )

        self.text_encoder_weight_dtype_combo = _build_dtype_combo()
        self.text_encoder_weight_dtype_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        self.text_encoder_2_weight_dtype_combo = _build_dtype_combo()
        self.text_encoder_2_weight_dtype_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        self.vae_weight_dtype_combo = _build_dtype_combo()
        self.vae_weight_dtype_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        # Mission 124: whether each Text Encoder actually gets a LoRA
        # adapter/gradients — independent of its weight_dtype above (see
        # src/domain/onetrainer_settings.py's own docstring). TE2's
        # visibility follows exactly the same architecture-driven rule
        # as text_encoder_2_weight_dtype_combo (see
        # _apply_architecture_to_dtype_fields() below), never a second
        # architecture check.
        self.text_encoder_train_combo = _build_text_encoder_train_combo()
        self.text_encoder_train_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        self.text_encoder_2_train_combo = _build_text_encoder_train_combo()
        self.text_encoder_2_train_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        # Mission 124: which LoRA layers actually receive an adapter —
        # valid for all three architectures, no visibility restriction.
        self.lora_layer_filter_combo = _build_lora_layer_filter_combo()
        self.lora_layer_filter_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        # Mission 122: optimizer selection — see
        # src/domain/onetrainer_optimizer_settings.py's own docstring and
        # MISSION_122.md section 3 for the full architectural contract.
        self.optimizer_combo = _build_optimizer_combo()
        self.optimizer_combo.currentIndexChanged.connect(self._on_training_parameters_changed)

        # Mission 126 section 2.5/2.6/2.7: flow-matching timestep/noise
        # settings — FLUX-only (see _apply_architecture_to_dtype_fields()
        # below for the visibility/reset contract, same pattern as
        # Text Encoder 2). timestep_distribution/dynamic_timestep_shifting
        # follow the exact same combo conventions as every other
        # dtype-style/tri-state field on this page.
        self.timestep_distribution_combo = _build_timestep_distribution_combo()
        self.timestep_distribution_combo.currentIndexChanged.connect(
            self._on_training_parameters_changed
        )

        self.dynamic_timestep_shifting_combo = _build_dynamic_timestep_shifting_combo()
        self.dynamic_timestep_shifting_combo.currentIndexChanged.connect(
            self._on_dynamic_timestep_shifting_changed
        )

        # Mission 126 section 2.7/7: timestep_shift is Optional[float] —
        # a QDoubleSpinBox alone cannot represent "not configured" as a
        # third state distinct from any real float (unlike the combos
        # above), hence a checkbox pairing instead of a sentinel value.
        # Unchecked -> Domain None; checked -> Domain = the spinbox's
        # current value, including 1.0 explicit (see
        # save_training_parameters() below).
        self.timestep_shift_checkbox = QCheckBox("Configurer le timestep shift")
        self.timestep_shift_checkbox.toggled.connect(self._on_timestep_shift_checkbox_toggled)

        # No OneTrainer-side min/max exists for this field (its own
        # official UI uses a free-text entry with no validation,
        # confirmed by direct inspection of modules/ui/TrainingTab.py —
        # see MISSION_126.md section 1) — this range is a purely
        # technical Qt bound wide enough to never truncate any
        # realistic value, never a Toolkit-imposed business limit.
        self.timestep_shift_spinbox = QDoubleSpinBox()
        self.timestep_shift_spinbox.setRange(-1000.0, 1000.0)
        self.timestep_shift_spinbox.setDecimals(3)
        self.timestep_shift_spinbox.setSingleStep(0.1)
        self.timestep_shift_spinbox.setValue(1.0)
        self.timestep_shift_spinbox.valueChanged.connect(self._on_training_parameters_changed)

        # Mission 126 section 8: initial enabled state — checkbox starts
        # unchecked, so the spinbox must start disabled too.
        self._apply_dynamic_timestep_shifting_ui_state()

        # Mission 125 section 6/7: "Basic settings" groups exactly the
        # fields a user must normally understand/modify to configure an
        # ordinary training run — classified by real usage, never by
        # historical addition order (see MISSION_125.md section 6 for the
        # full audit). Bold label added for visual symmetry with the
        # "Advanced settings" toggle immediately below, making the
        # Basic/Advanced separation explicit rather than implicit.
        basic_settings_label = QLabel("Basic settings")
        basic_settings_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(basic_settings_label)

        training_form = QFormLayout()
        training_form.addRow("Modèle de base :", base_model_field)
        training_form.addRow("Architecture :", self.architecture_combo)
        training_form.addRow("Résolution :", self.resolution_spinbox)
        training_form.addRow("Epochs :", self.epochs_spinbox)
        training_form.addRow("Learning rate :", self.learning_rate_spinbox)
        training_form.addRow("LoRA rank :", self.lora_rank_spinbox)
        training_form.addRow("LoRA alpha :", self.lora_alpha_spinbox)
        training_form.addRow("Trigger word :", self.trigger_word_edit)
        training_form.addRow("Batch size :", self.batch_size_spinbox)

        layout.addLayout(training_form)

        # Mission 121 section 7: a genuinely repliable section — a
        # QToolButton title/toggle plus a QWidget container whose only
        # changed property is `visible`. Deliberately NOT a checkable
        # QGroupBox: Qt's QGroupBox.setCheckable() conventionally means
        # "enable/disable this group's content" (it auto-disables its
        # children when unchecked), which would create a real ambiguity
        # here ("Advanced settings unchecked" could be misread as
        # "ignore the advanced settings") — see MISSION_121.md section 7
        # for the full rationale. Folding/unfolding never touches any
        # value and never marks the form dirty by itself — only
        # `_on_advanced_settings_toggled()` is connected to `toggled`.
        # Local to this Page only, not a generic Accordion abstraction.
        self.advanced_settings_toggle = QToolButton()
        self.advanced_settings_toggle.setText("Advanced settings")
        self.advanced_settings_toggle.setCheckable(True)
        self.advanced_settings_toggle.setArrowType(Qt.RightArrow)
        self.advanced_settings_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_settings_toggle.toggled.connect(self._on_advanced_settings_toggled)

        layout.addWidget(self.advanced_settings_toggle)

        self.advanced_settings_container = QWidget()
        self.advanced_settings_container.setVisible(False)

        advanced_settings_form = QFormLayout(self.advanced_settings_container)

        # Mission 125 section 6: reclassified from Basic to Advanced —
        # never surfaced by any of OneTrainer's own 3 official LoRA
        # presets (SD1.5/SDXL/FLUX all leave it at "CONSTANT", see
        # MISSION_125.md section 4), a specialized scheduling choice a
        # user does not need to understand for an ordinary training run.
        training_schedule_label = QLabel("Training schedule")
        training_schedule_label.setStyleSheet("font-weight:bold;")
        advanced_settings_form.addRow(training_schedule_label)

        advanced_settings_form.addRow(
            "Learning rate scheduler :", self.learning_rate_scheduler_combo
        )

        precision_memory_label = QLabel("Precision / Memory")
        precision_memory_label.setStyleSheet("font-weight:bold;")
        advanced_settings_form.addRow(precision_memory_label)

        advanced_settings_form.addRow("Training dtype :", self.train_dtype_combo)

        advanced_settings_form.addRow(
            "Gradient checkpointing :", self.gradient_checkpointing_combo
        )

        # Mission 125 section 6: reclassified from Basic to Advanced,
        # grouped here — a memory/technical trade-off (simulating a
        # larger effective batch size) never surfaced by any of the 3
        # official LoRA presets (MISSION_125.md section 4).
        advanced_settings_form.addRow(
            "Gradient accumulation steps :", self.gradient_accumulation_steps_spinbox
        )

        self.main_model_weight_dtype_label = QLabel("UNet weight dtype :")
        advanced_settings_form.addRow(
            self.main_model_weight_dtype_label, self.main_model_weight_dtype_combo
        )

        advanced_settings_form.addRow(
            "Text Encoder weight dtype :", self.text_encoder_weight_dtype_combo
        )
        advanced_settings_form.addRow(
            "Text Encoder train :", self.text_encoder_train_combo
        )

        self.text_encoder_2_weight_dtype_label = QLabel("Text Encoder 2 weight dtype :")
        advanced_settings_form.addRow(
            self.text_encoder_2_weight_dtype_label, self.text_encoder_2_weight_dtype_combo
        )
        self.text_encoder_2_train_label = QLabel("Text Encoder 2 train :")
        advanced_settings_form.addRow(
            self.text_encoder_2_train_label, self.text_encoder_2_train_combo
        )

        advanced_settings_form.addRow("VAE weight dtype :", self.vae_weight_dtype_combo)

        lora_layers_label = QLabel("LoRA layers")
        lora_layers_label.setStyleSheet("font-weight:bold;")
        advanced_settings_form.addRow(lora_layers_label)

        advanced_settings_form.addRow("Layer filter :", self.lora_layer_filter_combo)

        optimizer_label = QLabel("Optimizer")
        optimizer_label.setStyleSheet("font-weight:bold;")
        advanced_settings_form.addRow(optimizer_label)

        advanced_settings_form.addRow("Optimizer :", self.optimizer_combo)

        # Mission 126 section 2.9/9: visible only in FLUX architecture —
        # see _apply_architecture_to_dtype_fields() below, same
        # visibility mechanism as Text Encoder 2's own label+combo pairs.
        # Every widget here is kept as an instance attribute so its
        # visibility can be toggled as a group, never inferred from
        # QFormLayout row indices.
        self.flow_matching_section_label = QLabel("Flow-matching (FLUX)")
        self.flow_matching_section_label.setStyleSheet("font-weight:bold;")
        advanced_settings_form.addRow(self.flow_matching_section_label)

        self.timestep_distribution_label = QLabel("Timestep distribution :")
        advanced_settings_form.addRow(
            self.timestep_distribution_label, self.timestep_distribution_combo
        )

        self.dynamic_timestep_shifting_label = QLabel("Dynamic timestep shifting :")
        advanced_settings_form.addRow(
            self.dynamic_timestep_shifting_label, self.dynamic_timestep_shifting_combo
        )

        advanced_settings_form.addRow(self.timestep_shift_checkbox)

        self.timestep_shift_label = QLabel("Timestep shift :")
        advanced_settings_form.addRow(self.timestep_shift_label, self.timestep_shift_spinbox)

        layout.addWidget(self.advanced_settings_container)

        self.save_parameters_button = QPushButton("Enregistrer les paramètres d'entraînement")
        self.save_parameters_button.setEnabled(False)
        self.save_parameters_button.clicked.connect(self.save_training_parameters)

        layout.addWidget(self.save_parameters_button)

        # Mission 097: the mission's one orchestration entry point —
        # materializes the Dataset, builds and writes the OneTrainer
        # configuration, never starts OneTrainer (see MISSION_097.md
        # section 7/8 for the explicit boundary).
        self.prepare_config_button = QPushButton("Préparer la configuration OneTrainer")
        self.prepare_config_button.setEnabled(False)
        self.prepare_config_button.clicked.connect(self.prepare_onetrainer_config)

        layout.addWidget(self.prepare_config_button)

        # Mission 100: minimal execution UI — Start/Cancel, a coarse
        # state label, and raw stdout/stderr logs. No percentage bar
        # (callback.pipe is not consumed — see MISSION_100.md section
        # 7): if OneTrainer's own tqdm progress text is exploitable, it
        # simply appears as-is in job_log_view below, never parsed.
        job_buttons = QHBoxLayout()

        self.start_training_button = QPushButton("Démarrer l'entraînement")
        self.start_training_button.setEnabled(False)
        self.start_training_button.clicked.connect(self.start_training)

        self.cancel_training_button = QPushButton("Annuler")
        self.cancel_training_button.setEnabled(False)
        self.cancel_training_button.clicked.connect(self.cancel_training)

        job_buttons.addWidget(self.start_training_button)
        job_buttons.addWidget(self.cancel_training_button)

        layout.addLayout(job_buttons)

        self.job_state_label = QLabel("")

        layout.addWidget(self.job_state_label)

        self.job_log_view = QPlainTextEdit()
        self.job_log_view.setReadOnly(True)
        self.job_log_view.setMaximumBlockCount(2000)

        layout.addWidget(self.job_log_view)

        # Mission 103: minimal, persistent list of every TrainingJob of
        # the selected Training — never a log viewer or a monitoring
        # dashboard (MISSION_103.md section 3.2). Read directly from
        # Training.jobs (already Workspace-persisted since Mission 100),
        # no new storage. A single contextual action below acts on
        # whichever Job is currently selected in this list, same
        # established pattern as training_list/delete_button above.
        jobs_label = QLabel("Résultats des entraînements :")
        layout.addWidget(jobs_label)

        self.jobs_list = QListWidget()
        self.jobs_list.currentItemChanged.connect(self._on_job_selection_changed)

        layout.addWidget(self.jobs_list)

        self.import_lora_button = QPushButton("Importer dans la Bibliothèque LoRA centrale")
        self.import_lora_button.setEnabled(False)
        self.import_lora_button.clicked.connect(self.import_selected_job_to_library)

        layout.addWidget(self.import_lora_button)

        # Mission 109: distinct action from the import above — available
        # for any Job whose imported_lora_id still resolves to a real
        # Central Library LoRA, not only right after a fresh import.
        self.use_lora_in_inference_button = QPushButton("Utiliser dans Inference")
        self.use_lora_in_inference_button.setEnabled(False)
        self.use_lora_in_inference_button.clicked.connect(self.use_selected_lora_in_inference)

        layout.addWidget(self.use_lora_in_inference_button)

        self._refresh_job_controls()

    def create_training(self):

        # Mission 037: must precede the dataset lookup below — otherwise
        # "Aucun dataset disponible" fires when no Workspace is open at
        # all (DatasetManager.datasets is [] in both cases), masking the
        # real cause. See the Mission 037 specification for the full
        # ordering rationale.
        if not self.workspace_manager.opened:
            QMessageBox.warning(
                self,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer une session d'entraînement."
            )
            return

        datasets = self.dataset_manager.list_datasets()

        if not datasets:
            QMessageBox.warning(
                self,
                "Aucun dataset disponible",
                "Créez un dataset avant de créer une session d'entraînement."
            )
            return

        # Labels must stay unique even when two datasets share the same
        # name — the dataset_id fragment disambiguates them. The
        # mapping is local to this dialog, never persisted.
        label_to_id = {
            f"{dataset['name']} [{dataset['dataset_id'][:8]}]": dataset['dataset_id']
            for dataset in datasets
        }
        labels = list(label_to_id.keys())

        label, ok = QInputDialog.getItem(
            self, "Sélectionner un dataset", "Dataset :", labels, 0, False
        )

        if not ok or not label:
            return

        dataset_id = label_to_id[label]

        name, ok = QInputDialog.getText(self, "Nouvelle session", "Nom :")

        if not ok or not name.strip():
            return

        try:
            training = self.training_manager.create(name.strip(), dataset_id)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la nouvelle session dans le projet : {exc}\n"
                "La session n'a pas été créée."
            )
            return

        if training is None:
            # TrainingManager.create() now follows the Workspace's
            # principal Character (Mission 026/028), not a manual
            # selection the hidden multi-character UI no longer offers a
            # way to make — this can only fire for the genuine edge case
            # of a Workspace with zero Character at all (workspace_manager
            # is already guaranteed open at this point by the guard above).
            QMessageBox.warning(
                self,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une session d'entraînement."
            )

    def rename_training(self):

        if self.training_manager.active_training_id is None:
            return

        # Mission 070: update_name() rolls back Training.name before
        # re-raising on a save() failure — update_trainings() redraws
        # name_edit from that rolled-back Domain state, so no manual
        # widget restoration is needed beyond informing the user.
        try:
            self.training_manager.update_name(self.name_edit.text())
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le renommage dans le projet : {exc}\n"
                "Le nom précédent a été restauré."
            )
            self.update_trainings()

    def delete_training(self):

        item = self.training_list.currentItem()

        if item is None:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Supprimer la session d'entraînement ?")
        # Mission 105: the currently displayed parameter draft belongs to
        # this exact Training only when it is still the loaded one (it
        # always is here — this is the same list item currentItem() just
        # returned) — a single adapted dialog rather than a second,
        # separate confirmation, mirroring LoRAPage.delete_lora()'s intent
        # without stacking two dialogs in a row.
        if self._dirty and item.data(Qt.UserRole) == self._loaded_training_id:
            box.setText(
                f"Supprimer la session d'entraînement « {item.text()} » ? Cette "
                "action est irréversible et les paramètres non enregistrés de "
                "cette session seront perdus."
            )
        else:
            box.setText(
                f"Supprimer la session d'entraînement « {item.text()} » ? "
                "Cette action est irréversible."
            )
        delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not delete_button:
            return

        # Mission 068: delete() rolls back the Domain removal (and
        # active_training_id) before re-raising on a save() failure —
        # the training stays exactly where it was, so no refresh is
        # needed here beyond informing the user.
        try:
            self.training_manager.delete(item.data(Qt.UserRole))
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer la suppression dans le projet : {exc}\n"
                "La session d'entraînement n'a pas été supprimée."
            )

    def on_training_selection_changed(self, current, previous):

        # Mission 063: "Supprimer" must always reflect whether there is
        # currently something to delete — set regardless of the early
        # return just below, unlike training_manager.select() itself.
        self.delete_button.setEnabled(current is not None)
        # Mission 097: same treatment for the two new actions — nothing
        # to save or prepare without an active training.
        self.save_parameters_button.setEnabled(current is not None)
        self.prepare_config_button.setEnabled(current is not None)

        if current is None:
            self._refresh_job_controls()
            return

        # Mission 105: captured now, before any Manager call below can
        # reentrantly trigger update_trainings() -> training_list.clear(),
        # which deletes the underlying C++ QListWidgetItem `current`
        # wraps (e.g. save_training_parameters() calls TrainingManager.
        # update(), which publishes WORKSPACE_SAVED synchronously).
        # Reading current.data() again afterward would then raise. Same
        # precedent as LoRAPage/PromptsPage.
        target_training_id = current.data(Qt.UserRole)

        if self._dirty:
            choice = self._confirm_discard_training_before_switch()

            if choice == QMessageBox.Cancel:
                # Mission 105: training_manager.select() is never called
                # — active_training_id stays untouched. Revert the
                # widget's own native selection (already changed by Qt
                # before this handler ran) back to `previous`, with
                # signals blocked to avoid recursively re-entering this
                # same handler.
                self.training_list.blockSignals(True)
                self.training_list.setCurrentItem(previous)
                self.training_list.blockSignals(False)
                self.delete_button.setEnabled(previous is not None)
                self.save_parameters_button.setEnabled(previous is not None)
                self.prepare_config_button.setEnabled(previous is not None)
                return

            if choice == QMessageBox.Save:
                if not self.save_training_parameters():
                    # save_training_parameters()'s own error dialog is
                    # already shown, and it has already resynced the
                    # fields to the rolled-back Domain state — revert
                    # only the visual selection, exactly like Cancel
                    # above, so the switch itself does not proceed.
                    self.training_list.blockSignals(True)
                    self.training_list.setCurrentItem(previous)
                    self.training_list.blockSignals(False)
                    self.delete_button.setEnabled(previous is not None)
                    self.save_parameters_button.setEnabled(previous is not None)
                    self.prepare_config_button.setEnabled(previous is not None)
                    return

            self._dirty = False

        self.training_manager.select(target_training_id)
        self._refresh_job_controls()

    def _confirm_discard_training_before_switch(self):
        box = QMessageBox(self)
        box.setWindowTitle("Modifications non enregistrées")
        box.setText(
            "Les paramètres d'entraînement actuels contiennent des "
            "modifications non enregistrées. Que souhaitez-vous faire ?"
        )
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setButtonText(QMessageBox.Save, "Enregistrer")
        box.setButtonText(QMessageBox.Discard, "Ignorer les modifications")
        box.setButtonText(QMessageBox.Cancel, "Annuler")
        box.setDefaultButton(QMessageBox.Cancel)
        return box.exec()

    def confirm_context_change(self) -> bool:
        """
        Mission 105: same role/contract as LoRAPage.confirm_context_change()
        (Mission 078) — called by MainWindow before a Workspace switch
        (new_project()/open_project()) that would otherwise let
        reset_for_context_change() silently discard an unsaved parameter
        draft once current_workspace is replaced, too late for a genuine
        Save or Cancel. Also reused, same contract, from closeEvent()
        before closing the whole application — after the orthogonal
        confirm_no_active_training() guard (Mission 100): a genuinely
        active Job has produced no result yet, so it cannot be protected
        by any dirty-draft guard.
        """
        if not self._dirty:
            return True

        choice = self._confirm_discard_training_before_switch()

        if choice == QMessageBox.Cancel:
            return False

        if choice == QMessageBox.Save:
            if not self.save_training_parameters():
                # save_training_parameters()'s own error dialog is
                # already shown — never re-inspect _dirty here (it is
                # already False again, resynced to the rolled-back
                # Domain state by the same failure branch).
                return False

        self._dirty = False
        return True

    def update_trainings(self, _payload=None):
        # Mission 105: subscribed (see main_window.py) only to
        # WORKSPACE_SAVED/RENAMED, CHARACTER_CREATED and TRAINING_CREATED/
        # SELECTED/DELETED — WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are handled exclusively by
        # reset_for_context_change() below, and a real Training switch is
        # handled by on_training_selection_changed() before
        # TRAINING_SELECTED is even published — so this dirty-draft
        # protection never depends on subscriber ordering.

        trainings = sorted(
            self.training_manager.list_trainings(),
            key=lambda training: training["name"].lower(),
        )
        active_training_id = self.training_manager.active_training_id

        self.training_list.blockSignals(True)
        self.training_list.clear()

        active_dataset_id = ""
        active_name = ""
        active_training = None

        for training in trainings:

            item = QListWidgetItem(training["name"])
            item.setData(Qt.UserRole, training["training_id"])

            self.training_list.addItem(item)

            if training["training_id"] == active_training_id:
                self.training_list.setCurrentItem(item)
                active_dataset_id = training["dataset_id"]
                active_name = training["name"]
                active_training = training

        self.training_list.blockSignals(False)
        # Mission 063: blockSignals() above suppresses currentItemChanged,
        # so setCurrentItem()/clear() never reach on_training_selection_changed()
        # during a rebuild — the buttons' state must be recomputed here.
        has_active = self.training_list.currentItem() is not None
        self.delete_button.setEnabled(has_active)
        self.save_parameters_button.setEnabled(has_active)
        self.prepare_config_button.setEnabled(has_active)

        # Mission 105: name_edit/dataset_label have no dirty-state of
        # their own (name_edit saves immediately on blur, mirroring
        # LoRAPage) — always resynced regardless of _dirty, unchanged
        # from their pre-existing behavior.
        self.name_edit.setText(active_name)
        self.dataset_label.setText(self._describe_dataset(active_dataset_id))

        if active_training_id != self._loaded_training_id or not self._dirty:
            # Either the active Training genuinely changed (e.g.
            # TRAINING_DELETED cleared it, or TRAINING_SELECTED/
            # TRAINING_CREATED made a different one active) — the 8
            # parameter fields must reflect the new Training, never the
            # previous one's draft — or nothing is actually dirty, in
            # which case refreshing is harmless and must still reflect a
            # mutation applied directly through TrainingManager.update()
            # outside this Page's own save_training_parameters() (e.g.
            # by another code path or test).
            self._load_training_parameters(active_training)
            self._loaded_training_id = active_training_id
        # else: a real unsaved parameter draft on the still-active
        # Training — non-destructive refresh (e.g. WORKSPACE_SAVED fired
        # by an unrelated Dataset/Character/etc. mutation elsewhere) —
        # the parameter fields are left untouched.

        self._refresh_job_controls()

    def _load_training_parameters(self, active_training):
        # Mission 105: unconditional — bypasses the parameters dirty-
        # state guard on purpose. Called whenever the active Training
        # actually changed (update_trainings()/reset_for_context_change())
        # or by a forced resync (_force_refresh_training_parameters(),
        # used by save_training_parameters()'s failure-rollback path).
        # Mirrors LoRAPage._load_metadata_fields(). Mission 120 extends
        # this to the 3 new parameter fields (batch_size/
        # gradient_accumulation_steps/learning_rate_scheduler), same
        # contract as the 8 pre-existing ones.
        fields = (
            self.base_model_edit,
            self.architecture_combo,
            self.resolution_spinbox,
            self.epochs_spinbox,
            self.learning_rate_spinbox,
            self.lora_rank_spinbox,
            self.lora_alpha_spinbox,
            self.trigger_word_edit,
            self.batch_size_spinbox,
            self.gradient_accumulation_steps_spinbox,
            self.learning_rate_scheduler_combo,
            self.train_dtype_combo,
            self.gradient_checkpointing_combo,
            self.main_model_weight_dtype_combo,
            self.text_encoder_weight_dtype_combo,
            self.text_encoder_2_weight_dtype_combo,
            self.vae_weight_dtype_combo,
            self.optimizer_combo,
            self.timestep_distribution_combo,
            self.dynamic_timestep_shifting_combo,
            self.timestep_shift_checkbox,
            self.timestep_shift_spinbox,
        )

        for field in fields:
            field.blockSignals(True)

        self.base_model_edit.setText(active_training["base_model_source"] if active_training else "")

        architecture = active_training["architecture"] if active_training else ""
        index = self.architecture_combo.findText(architecture) if architecture else -1
        self.architecture_combo.setCurrentIndex(index)

        # Mission 097: Training.resolution's own "0 means not yet
        # configured" sentinel (see its docstring) is a Domain-level
        # concept only — resolution_spinbox's range starts at 64 (no
        # real resolution is ever meaningfully below that), so 0 is
        # never displayed literally; a genuinely unset training simply
        # shows 64 until an architecture suggests a real value (see
        # on_architecture_changed() below) or the architect edits it.
        saved_resolution = active_training["resolution"] if active_training else 0
        self.resolution_spinbox.setValue(saved_resolution if saved_resolution else 64)
        self.epochs_spinbox.setValue(active_training["epochs"] if active_training else 1)
        self.learning_rate_spinbox.setValue(active_training["learning_rate"] if active_training else 0.0)
        self.lora_rank_spinbox.setValue(active_training["lora_rank"] if active_training else 1)
        self.lora_alpha_spinbox.setValue(active_training["lora_alpha"] if active_training else 0.0)
        self.trigger_word_edit.setText(active_training["trigger_word"] if active_training else "")

        # Mission 120: unlike resolution above, 0 is displayed literally
        # here (via setSpecialValueText("(non configuré)")) — there is
        # no architecture-suggested fallback for either field, so the
        # Domain's own "not configured" sentinel is shown as-is.
        self.batch_size_spinbox.setValue(active_training["batch_size"] if active_training else 0)
        self.gradient_accumulation_steps_spinbox.setValue(
            active_training["gradient_accumulation_steps"] if active_training else 0
        )

        onetrainer_settings = active_training["onetrainer_settings"] if active_training else {}
        learning_rate_scheduler = onetrainer_settings.get("learning_rate_scheduler", "")
        scheduler_index = self.learning_rate_scheduler_combo.findData(learning_rate_scheduler)
        self.learning_rate_scheduler_combo.setCurrentIndex(scheduler_index if scheduler_index != -1 else 0)

        # Mission 121: real persisted values for the two mutually-
        # exclusive main-model drafts are both loaded here, independent
        # of which one is currently displayed — _apply_architecture_to_
        # dtype_fields() below (reset_incompatible=False, this is a
        # genuine reload, never a user-driven switch) then picks the
        # right one to show for this Training's own architecture,
        # without discarding the other's real stored value.
        self._unet_weight_dtype_draft = onetrainer_settings.get("unet_weight_dtype", "")
        self._transformer_weight_dtype_draft = onetrainer_settings.get("transformer_weight_dtype", "")

        train_dtype = onetrainer_settings.get("train_dtype", "")
        train_dtype_index = self.train_dtype_combo.findData(train_dtype)
        self.train_dtype_combo.setCurrentIndex(train_dtype_index if train_dtype_index != -1 else 0)

        gradient_checkpointing_mode = onetrainer_settings.get("gradient_checkpointing_mode", "")
        gradient_checkpointing_index = self.gradient_checkpointing_combo.findData(
            gradient_checkpointing_mode
        )
        self.gradient_checkpointing_combo.setCurrentIndex(
            gradient_checkpointing_index if gradient_checkpointing_index != -1 else 0
        )

        text_encoder_weight_dtype = onetrainer_settings.get("text_encoder_weight_dtype", "")
        text_encoder_index = self.text_encoder_weight_dtype_combo.findData(text_encoder_weight_dtype)
        self.text_encoder_weight_dtype_combo.setCurrentIndex(
            text_encoder_index if text_encoder_index != -1 else 0
        )

        text_encoder_2_weight_dtype = onetrainer_settings.get("text_encoder_2_weight_dtype", "")
        text_encoder_2_index = self.text_encoder_2_weight_dtype_combo.findData(
            text_encoder_2_weight_dtype
        )
        self.text_encoder_2_weight_dtype_combo.setCurrentIndex(
            text_encoder_2_index if text_encoder_2_index != -1 else 0
        )

        vae_weight_dtype = onetrainer_settings.get("vae_weight_dtype", "")
        vae_index = self.vae_weight_dtype_combo.findData(vae_weight_dtype)
        self.vae_weight_dtype_combo.setCurrentIndex(vae_index if vae_index != -1 else 0)

        # Mission 124: text_encoder_train/text_encoder_2_train — the
        # dict value is already a real None/True/False (this reads
        # Training.to_dict()'s own already-typed nested dict, never raw
        # disk JSON), so findData() matches exactly without any
        # fallback-to-index-0 ambiguity between "not configured" and
        # "value not representable here" (unlike optimizer/scheduler,
        # every real value here IS representable).
        text_encoder_train = onetrainer_settings.get("text_encoder_train")
        self.text_encoder_train_combo.setCurrentIndex(
            self.text_encoder_train_combo.findData(text_encoder_train)
        )

        text_encoder_2_train = onetrainer_settings.get("text_encoder_2_train")
        self.text_encoder_2_train_combo.setCurrentIndex(
            self.text_encoder_2_train_combo.findData(text_encoder_2_train)
        )

        lora_layer_filter = onetrainer_settings.get("lora_layer_filter", "")
        lora_layer_filter_index = self.lora_layer_filter_combo.findData(lora_layer_filter)
        self.lora_layer_filter_combo.setCurrentIndex(
            lora_layer_filter_index if lora_layer_filter_index != -1 else 0
        )

        # Mission 122: optimizer discriminant lives one level deeper,
        # under onetrainer_settings["optimizer_settings"]["optimizer"] —
        # never confused with the flat dtype/scheduler fields above. A
        # value stored outside the 3 UI-proposed choices (e.g. via
        # extra_overrides-era hand editing, or a future wider UI) falls
        # back to index 0 ("(non configuré)") in this combo only —
        # never lost at the Domain level, only not representable here.
        optimizer_settings = onetrainer_settings.get("optimizer_settings", {})
        optimizer = optimizer_settings.get("optimizer", "") if isinstance(optimizer_settings, dict) else ""
        optimizer_index = self.optimizer_combo.findData(optimizer)
        self.optimizer_combo.setCurrentIndex(optimizer_index if optimizer_index != -1 else 0)

        # Mission 126: timestep_distribution follows the same "" sentinel
        # combo pattern as lora_layer_filter above.
        timestep_distribution = onetrainer_settings.get("timestep_distribution", "")
        timestep_distribution_index = self.timestep_distribution_combo.findData(
            timestep_distribution
        )
        self.timestep_distribution_combo.setCurrentIndex(
            timestep_distribution_index if timestep_distribution_index != -1 else 0
        )

        # dynamic_timestep_shifting/timestep_shift — same already-typed
        # None/True/False (resp. None/float) precedent as
        # text_encoder_train above: this reads Training.to_dict()'s own
        # already-typed nested dict, never raw disk JSON, so findData()
        # matches exactly. timestep_shift has no combo — the checkbox
        # reflects "configured or not" and the spinbox reflects the
        # value, restored independently of dynamic_timestep_shifting's
        # own value (MISSION_126.md section 2.8: configuring one never
        # mutates the other).
        dynamic_timestep_shifting = onetrainer_settings.get("dynamic_timestep_shifting")
        self.dynamic_timestep_shifting_combo.setCurrentIndex(
            self.dynamic_timestep_shifting_combo.findData(dynamic_timestep_shifting)
        )

        timestep_shift = onetrainer_settings.get("timestep_shift")
        self.timestep_shift_checkbox.setChecked(timestep_shift is not None)
        self.timestep_shift_spinbox.setValue(timestep_shift if timestep_shift is not None else 1.0)

        # Reflects the right main-model field/label/Text-Encoder-2
        # visibility for this Training's own architecture — never a
        # reset, this is a genuine reload of already-persisted values.
        self._apply_architecture_to_dtype_fields(architecture, reset_incompatible=False)

        for field in fields:
            field.blockSignals(False)

        # Mission 126 section 8: blockSignals() above suppressed the
        # currentIndexChanged/toggled handlers that would normally keep
        # timestep_shift's enabled state in sync — recomputed explicitly
        # once here instead, after every field reflects the reloaded
        # Training.
        self._apply_dynamic_timestep_shifting_ui_state()

        self._dirty = False

    def _force_refresh_training_parameters(self):
        # Mission 105: bypasses the dirty-state guard entirely — used by
        # save_training_parameters()'s failure-rollback path, which must
        # always reflect the just-restored Domain state, never a stale
        # or rejected view. Mirrors LoRAPage._force_refresh_lora(),
        # scoped to the parameter fields only (training_list/name_edit/
        # dataset_label never change on this failure).
        active_training_id = self.training_manager.active_training_id
        active_training = None
        if active_training_id is not None:
            for training in self.training_manager.list_trainings():
                if training["training_id"] == active_training_id:
                    active_training = training
                    break

        self._load_training_parameters(active_training)
        self._loaded_training_id = active_training_id

    def reset_for_context_change(self, _payload=None):
        """
        Mission 105: subscribed by MainWindow to WORKSPACE_CREATED/
        OPENED/CLOSED and CHARACTER_SELECTED/DELETED — never to
        update_trainings()'s own events. A naive active_training_id vs
        _loaded_training_id comparison would wrongly read None == None
        as "nothing changed" when switching between two Workspaces that
        both happen to leave no Training active — silently carrying a
        stray draft across a genuine Workspace/Character switch. This
        method is therefore the sole, unconditional Presentation path
        for these 5 events, mirroring LoRAPage.reset_for_context_change()
        (Mission 078).
        """
        self.training_list.blockSignals(True)
        self.training_list.clear()
        self.training_list.blockSignals(False)

        self.delete_button.setEnabled(False)
        self.save_parameters_button.setEnabled(False)
        self.prepare_config_button.setEnabled(False)

        self.name_edit.setText("")
        self.dataset_label.setText("")

        self._load_training_parameters(None)
        self._loaded_training_id = None

        self._refresh_job_controls()

    def _describe_dataset(self, dataset_id):

        if not dataset_id:
            return ""

        for dataset in self.dataset_manager.list_datasets():
            if dataset["dataset_id"] == dataset_id:
                return f"Dataset : {dataset['name']} [{dataset_id[:8]}]"

        return f"Dataset introuvable [{dataset_id}]"

    def browse_base_model_source(self):
        # Mission 097 section 3.3: only the local-file form is actively
        # exposed by this mission's UI — a Diffusers folder or a Hugging
        # Face identifier both remain reachable by typing/pasting
        # directly into base_model_edit, deliberately not offered a
        # dedicated picker here (see MISSION_097.md section 3.3 for the
        # scope decision).
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un modèle de base",
            "",
            "Modèles (*.safetensors *.ckpt)"
        )

        if not file_path:
            return

        self.base_model_edit.setText(file_path)

    def on_architecture_changed(self, architecture):
        # Mission 097 section 3.7: only ever fires on a genuine user
        # selection — update_trainings()/_load_training_parameters()
        # block this signal while reloading a training's own saved
        # architecture, so a stored resolution is never silently
        # overwritten by this suggestion, and a programmatic reload
        # never marks the form dirty by itself.
        #
        # Mission 105: marks the form dirty here rather than adding a
        # second connection to currentTextChanged — this is the only
        # place that signal is (and needs to be) handled.
        self._dirty = True

        suggested_resolution = _SUGGESTED_RESOLUTION_BY_ARCHITECTURE.get(architecture)
        if suggested_resolution is not None:
            self.resolution_spinbox.setValue(suggested_resolution)

        self._apply_architecture_to_dtype_fields(architecture, reset_incompatible=True)

    def _apply_architecture_to_dtype_fields(self, architecture: str, reset_incompatible: bool):
        """
        Mission 121 section 3.3/7: recomputes, for the given
        architecture, (1) which of the two mutually-exclusive "main
        model" components applies (unet for SD15/SDXL, transformer for
        FLUX) and its row label, and (2) whether Text Encoder 2 is a
        real component for this architecture (absent for SD15).

        When `reset_incompatible` is True (a genuine user-driven
        architecture change, never a programmatic reload of an already-
        saved Training — see _load_training_parameters() below, which
        calls this with False), any field that becomes incompatible
        with the new architecture is explicitly reset to "" — never
        left silently carried over out of view, never resurfacing later
        in the same editing session if the architecture is switched
        back. A field that stays compatible across the change (e.g.
        unet_weight_dtype across SD15 <-> SDXL) is never touched.
        """
        new_main_model_field = (
            "transformer_weight_dtype"
            if architecture == TRAINING_ARCHITECTURE_FLUX
            else "unet_weight_dtype"
        )

        if reset_incompatible and new_main_model_field != self._main_model_dtype_field:
            if self._main_model_dtype_field == "unet_weight_dtype":
                self._unet_weight_dtype_draft = ""
            else:
                self._transformer_weight_dtype_draft = ""

        self._main_model_dtype_field = new_main_model_field

        self.main_model_weight_dtype_label.setText(
            "Transformer weight dtype :"
            if new_main_model_field == "transformer_weight_dtype"
            else "UNet weight dtype :"
        )

        active_draft = (
            self._transformer_weight_dtype_draft
            if new_main_model_field == "transformer_weight_dtype"
            else self._unet_weight_dtype_draft
        )
        index = self.main_model_weight_dtype_combo.findData(active_draft)
        self.main_model_weight_dtype_combo.setCurrentIndex(index if index != -1 else 0)

        text_encoder_2_applies = architecture != TRAINING_ARCHITECTURE_SD15
        self.text_encoder_2_weight_dtype_label.setVisible(text_encoder_2_applies)
        self.text_encoder_2_weight_dtype_combo.setVisible(text_encoder_2_applies)
        # Mission 124: text_encoder_2_train follows exactly the same
        # architecture-driven visibility as its dtype sibling above —
        # never a second architecture check.
        self.text_encoder_2_train_label.setVisible(text_encoder_2_applies)
        self.text_encoder_2_train_combo.setVisible(text_encoder_2_applies)

        if reset_incompatible and not text_encoder_2_applies:
            index = self.text_encoder_2_weight_dtype_combo.findData("")
            self.text_encoder_2_weight_dtype_combo.setCurrentIndex(index)
            # Index 0 is always "Non configuré" (None) by construction
            # of _build_text_encoder_train_combo() — never resurfaces a
            # now-invalid True/False for SD1.5 later in the same
            # editing session, same guarantee as the dtype reset above.
            self.text_encoder_2_train_combo.setCurrentIndex(0)

        # Mission 126 section 2.9/9: the "Flow-matching (FLUX)" section
        # follows the same architecture-driven visibility rule as
        # Text Encoder 2 above — visible only in FLUX, invisible (never
        # destroyed) for SD1.5/SDXL.
        flow_matching_applies = architecture == TRAINING_ARCHITECTURE_FLUX
        for widget in (
            self.flow_matching_section_label,
            self.timestep_distribution_label,
            self.timestep_distribution_combo,
            self.dynamic_timestep_shifting_label,
            self.dynamic_timestep_shifting_combo,
            self.timestep_shift_checkbox,
            self.timestep_shift_label,
            self.timestep_shift_spinbox,
        ):
            widget.setVisible(flow_matching_applies)

        if reset_incompatible and not flow_matching_applies:
            # Mission 126 section 9: a genuine user-driven move away
            # from FLUX explicitly resets all three flow-matching fields
            # to their sentinel — never left silently carried over out
            # of view, never resurfacing later in the same editing
            # session if the architecture is switched back to FLUX,
            # same principle as the Text Encoder 2 reset above.
            index = self.timestep_distribution_combo.findData("")
            self.timestep_distribution_combo.setCurrentIndex(index)
            # Index 0 is always "Non configuré" (None) by construction
            # of _build_dynamic_timestep_shifting_combo() — this also
            # fires _on_dynamic_timestep_shifting_changed(), which
            # recomputes the checkbox/spinbox enabled state below.
            self.dynamic_timestep_shifting_combo.setCurrentIndex(0)
            self.timestep_shift_checkbox.setChecked(False)

    def _on_main_model_weight_dtype_changed(self, _index=None):
        # Mission 121: writes the edited value into whichever of the
        # two mutually-exclusive drafts is currently active — never
        # both, never the wrong one.
        value = self.main_model_weight_dtype_combo.currentData()
        if self._main_model_dtype_field == "unet_weight_dtype":
            self._unet_weight_dtype_draft = value
        else:
            self._transformer_weight_dtype_draft = value
        self._on_training_parameters_changed()

    def _apply_dynamic_timestep_shifting_ui_state(self):
        """
        Mission 126 section 8: purely visual, never touches any Domain
        value. When dynamic_timestep_shifting is Activé (True),
        OneTrainer ignores timestep_shift's own value at runtime — the
        checkbox and spinbox are disabled to reflect that, but neither
        is unchecked/cleared: the previously entered value stays intact
        in the Domain and becomes editable again the moment
        dynamic_timestep_shifting is set back to Désactivé/Non
        configuré. Called on every genuine edit of either control, and
        once explicitly after a programmatic reload (blockSignals()
        during _load_training_parameters() suppresses the signals that
        would otherwise trigger this).
        """
        dynamic_active = self.dynamic_timestep_shifting_combo.currentData() is True
        self.timestep_shift_checkbox.setEnabled(not dynamic_active)
        self.timestep_shift_spinbox.setEnabled(
            self.timestep_shift_checkbox.isChecked() and not dynamic_active
        )

    def _on_dynamic_timestep_shifting_changed(self, _index=None):
        # Mission 126 section 8: a genuine user edit — recomputes the
        # timestep_shift controls' enabled state and marks the form
        # dirty, same two-step pattern as
        # _on_main_model_weight_dtype_changed() above.
        self._apply_dynamic_timestep_shifting_ui_state()
        self._on_training_parameters_changed()

    def _on_timestep_shift_checkbox_toggled(self, _checked=None):
        # Mission 126 section 7: toggling "Configurer le timestep shift"
        # is itself a real, dirty-marking Domain edit (checked ->
        # Domain becomes the spinbox's value; unchecked -> Domain
        # becomes None) — never confused with the purely-visual
        # disabling driven by dynamic_timestep_shifting above.
        self._apply_dynamic_timestep_shifting_ui_state()
        self._on_training_parameters_changed()

    def _on_advanced_settings_toggled(self, checked: bool):
        # Mission 121 section 7: purely visual — never touches any
        # field value, never marks the form dirty (this is the only
        # handler connected to `toggled`; each dtype combo's own
        # currentIndexChanged is what marks dirty on a genuine edit).
        self.advanced_settings_container.setVisible(checked)
        self.advanced_settings_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _on_training_parameters_changed(self, _value=None):
        # Mission 105: connected to the textChanged/valueChanged/
        # currentIndexChanged signal of each parameter widget except
        # architecture_combo (handled directly by on_architecture_
        # changed() above) — Mission 120 connects its 3 new widgets the
        # same way. Never
        # fires during a programmatic load protected by
        # _load_training_parameters()'s blockSignals() — genuine user
        # editing (including browse_base_model_source()'s setText()) is
        # the only way this can run.
        self._dirty = True

    def save_training_parameters(self) -> bool:
        """
        Mission 105: returns True only on genuine success. On failure,
        the pre-existing (Mission 097) contract resyncs the widgets to
        the just-rolled-back Domain state and informs the user their
        edit was not kept — the same "discard and resync" contract
        LoRAPage.save_metadata() already uses, unlike PromptsPage.
        save_text()'s "preserve the draft" contract. This means _dirty
        ends up False either way (there is genuinely nothing left
        unsaved once the widgets reflect reality again) — callers that
        need to distinguish success from failure (prepare_onetrainer_
        config()/start_training() below) must check this return value,
        never re-inspect _dirty afterward.
        """

        if self.training_manager.active_training_id is None:
            return False

        architecture = self.architecture_combo.currentText()

        try:
            self.training_manager.update(
                base_model_source=self.base_model_edit.text(),
                architecture=architecture,
                resolution=self.resolution_spinbox.value(),
                epochs=self.epochs_spinbox.value(),
                learning_rate=self.learning_rate_spinbox.value(),
                lora_rank=self.lora_rank_spinbox.value(),
                lora_alpha=self.lora_alpha_spinbox.value(),
                trigger_word=self.trigger_word_edit.text(),
                batch_size=self.batch_size_spinbox.value(),
                gradient_accumulation_steps=self.gradient_accumulation_steps_spinbox.value(),
                learning_rate_scheduler=self.learning_rate_scheduler_combo.currentData(),
                # Mission 121: unet_weight_dtype/transformer_weight_dtype
                # are persisted from the two tracked drafts, never from
                # the shared combo's own currentData() alone — only one
                # of the two is ever visible/edited at a time, but both
                # must be written on every Save so that switching
                # architecture back and forth within the same session
                # (with its explicit resets, see on_architecture_changed())
                # is reflected exactly, on both fields, every time.
                train_dtype=self.train_dtype_combo.currentData(),
                gradient_checkpointing_mode=self.gradient_checkpointing_combo.currentData(),
                unet_weight_dtype=self._unet_weight_dtype_draft,
                transformer_weight_dtype=self._transformer_weight_dtype_draft,
                text_encoder_weight_dtype=self.text_encoder_weight_dtype_combo.currentData(),
                text_encoder_2_weight_dtype=self.text_encoder_2_weight_dtype_combo.currentData(),
                vae_weight_dtype=self.vae_weight_dtype_combo.currentData(),
                optimizer=self.optimizer_combo.currentData(),
                text_encoder_train=self.text_encoder_train_combo.currentData(),
                text_encoder_2_train=self.text_encoder_2_train_combo.currentData(),
                lora_layer_filter=self.lora_layer_filter_combo.currentData(),
                timestep_distribution=self.timestep_distribution_combo.currentData(),
                dynamic_timestep_shifting=self.dynamic_timestep_shifting_combo.currentData(),
                # Mission 126 section 7: the checkbox is the sole source
                # of "configured or not" — unchecked always means None,
                # even if a numeric value remains displayed in the
                # (disabled) spinbox, checked always means the spinbox's
                # current value, including 1.0 explicit.
                timestep_shift=(
                    self.timestep_shift_spinbox.value()
                    if self.timestep_shift_checkbox.isChecked()
                    else None
                ),
            )
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer les paramètres d'entraînement dans le projet : {exc}\n"
                "Les valeurs précédentes ont été restaurées."
            )
            # Mission 105: unconditional resync to the just-rolled-back
            # Domain state — update_trainings() would wrongly skip this
            # while _dirty is still True and the active Training hasn't
            # changed, exactly the case _force_refresh_training_parameters()
            # exists to bypass (same precedent as LoRAPage's failure sites).
            self._force_refresh_training_parameters()
            return False

        # Mission 105: the save intent is satisfied here regardless of
        # update()'s own True/False return — its idempotent False (every
        # value already matches the persisted Training) still means
        # nothing is left unsaved from the UI's point of view.
        self._dirty = False

        return True

    def prepare_onetrainer_config(self):
        """
        Mission 097: the mission's one real orchestration action —
        materializes the active training's Dataset and writes a real
        OneTrainer configuration file. Never starts OneTrainer, never
        touches the network or the GPU (see MISSION_097.md section
        7/8) — this method's own body never imports or calls anything
        beyond TrainingManager.prepare_onetrainer_config().

        Mission 105: if the form is dirty, the currently displayed
        values are saved first — save_training_parameters()'s own
        failure already shows its own error dialog and returns False
        (never re-inspect _dirty afterward: a failed save resyncs the
        widgets to the rolled-back Domain state and clears _dirty too,
        same "discard and resync" contract as LoRAPage.save_metadata()),
        which this method treats as "stop here", never calling
        TrainingManager.prepare_onetrainer_config() against a save that
        did not actually happen.
        """

        training_id = self.training_manager.active_training_id

        if training_id is None:
            return

        if self._dirty:
            if not self.save_training_parameters():
                return

        try:
            result = self.training_manager.prepare_onetrainer_config(training_id)
        except (TrainingPreparationError, OneTrainerConfigError) as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de préparer la configuration OneTrainer : {exc}"
            )
            return

        QMessageBox.information(
            self,
            "Configuration préparée",
            "La configuration OneTrainer a été préparée avec succès :\n\n"
            f"Concept : {result.concept_path}\n"
            f"Configuration : {result.config_path}\n"
            f"Résultat attendu : {result.output_path}\n\n"
            "Aucun entraînement n'a été lancé."
        )

    def is_training_active(self) -> bool:
        """
        Mission 100 section 11 (close guard): the Domain-level source of
        truth (TrainingManager.has_active_job()) — never this Page's own
        `self._active_runner`, which only reflects this particular Page
        instance's own in-flight Job, not the persisted Job state that
        survives across Page rebuilds within the same session.
        """
        return self.training_manager.has_active_job()

    def confirm_no_active_training(self, blocked_message: str) -> bool:
        """
        Mission 100 section 11: same True=proceed/False=abandon contract
        as InferencePage.confirm_no_active_generation() (Mission 085) —
        never merged with it, a different Manager/Domain entity entirely.
        """
        if not self.is_training_active():
            return True

        QMessageBox.warning(self, "Entraînement en cours", blocked_message)
        return False

    def start_training(self):
        """
        Mission 100: the mission's real execution entry point — creates
        a TrainingJob (Training-scoped Prepare stays untouched) and
        drives it via a TrainingJobRunner. Revalidates OneTrainer's
        launch preconditions itself (via the runner, section 6) even
        though start_training_button is only enabled when
        _refresh_job_controls() last saw them satisfied — a path valid
        when the UI was drawn may have become invalid by the time this
        runs.

        Pre-M124 correction: guarantees that the parameters visible at
        the moment Start is clicked are the ones actually used by the
        new Job. create_job() itself only ever reads the
        onetrainer_config.json already written by the last successful
        TrainingManager.prepare_onetrainer_config() call — never the
        widgets, never the Training object directly — so a dirty form
        is saved first, and Prepare is now called unconditionally,
        every time, right before create_job(). The former conditional
        (only re-Prepare when a session-local `_config_stale` flag was
        True) tracked "was an edit detected since the parameter widgets
        were last (re)loaded" — a purely in-memory, per-page-instance
        signal that is wiped by any reload of those widgets (switching
        to another Training and back, or an application restart),
        with no relation to whether onetrainer_config.json on disk
        still matched this Training's real, persisted state. A Training
        never explicitly Prepared, or one whose file had gone stale
        across such a reload, could therefore reach create_job() with
        either no file at all (raising a raw, English, internal
        TrainingJobError) or a stale one (silently starting a real job
        with outdated parameters, no error at all). Preparing
        unconditionally removes the dependency on that flag entirely —
        create_job() still checks the file exists (defensive, but no
        longer the only thing standing between a Start click and a
        stale run), never a freshness guarantee by itself anymore.
        Prepare itself is cheap and side-effect-free beyond local
        filesystem I/O (dataset materialization + a JSON write, no
        GPU/network/OneTrainer process — see TrainingManager.
        prepare_onetrainer_config()'s own docstring) and idempotent, so
        calling it every time, even when nothing changed, is safe.
        """
        training_id = self.training_manager.active_training_id

        if training_id is None or self._active_runner is not None:
            return

        if self._dirty:
            if not self.save_training_parameters():
                # save_training_parameters()'s own error dialog is
                # already shown — never re-inspect _dirty here (a
                # failed save resyncs the widgets and clears it too,
                # same contract as prepare_onetrainer_config() above) —
                # no Job is created against a save that did not happen.
                return

        try:
            self.training_manager.prepare_onetrainer_config(training_id)
        except (TrainingPreparationError, OneTrainerConfigError) as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible de préparer la configuration OneTrainer avant "
                f"le démarrage : {exc}"
            )
            return

        try:
            job = self.training_manager.create_job(training_id)
        except TrainingJobError as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de démarrer l'entraînement : {exc}")
            return
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le démarrage de l'entraînement dans le projet : {exc}\n"
                "L'entraînement n'a pas été démarré."
            )
            return

        self._active_job_id = job.job_id
        self._cancel_in_flight = False
        self.job_log_view.clear()

        job_paths = self.training_manager.job_paths(training_id, job.job_id)
        onetrainer_path = self.application_settings_manager.settings.onetrainer_path

        self._active_runner = TrainingJobRunner(job_paths, onetrainer_path)
        self._active_runner.started.connect(self._on_job_started)
        self._active_runner.log_line.connect(self._on_job_log_line)
        self._active_runner.finished.connect(self._on_job_finished)
        self._active_runner.start()

        self._refresh_job_controls()

    def cancel_training(self):
        if self._active_runner is None:
            return

        self._cancel_in_flight = True
        self._active_runner.cancel()
        self._refresh_job_controls()

    def _on_job_started(self):
        # Mission 100 section 5.2: "running" is only ever set once the
        # OneTrainer subprocess is confirmed started by QProcess itself
        # — never assumed the moment start_training() returns.
        try:
            self.training_manager.update_job_state(self._active_job_id, TRAINING_JOB_STATE_RUNNING)
        except WorkspaceManagerError as exc:
            QMessageBox.warning(
                self,
                "Avertissement",
                f"L'entraînement a bien démarré mais son état n'a pas pu être enregistré "
                f"dans le projet : {exc}"
            )
        self._refresh_job_controls()

    def _on_job_log_line(self, line: str):
        self.job_log_view.appendPlainText(line)

    def _on_job_finished(self, state: str, error_message: str, final_output_path: str):
        kwargs = {}
        if error_message:
            kwargs["error_message"] = error_message
        if final_output_path:
            kwargs["final_output_path"] = final_output_path

        try:
            self.training_manager.update_job_state(self._active_job_id, state, **kwargs)
        except WorkspaceManagerError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'enregistrer le résultat de l'entraînement dans le projet : {exc}"
            )

        self._active_runner = None
        self._active_job_id = None
        self._cancel_in_flight = False
        self._refresh_job_controls()

        if state == "succeeded":
            QMessageBox.information(
                self,
                "Entraînement terminé",
                f"Entraînement terminé avec succès.\n\nLoRA produit : {final_output_path}"
            )
        elif state == "failed":
            QMessageBox.critical(
                self,
                "Entraînement échoué",
                error_message or "L'entraînement a échoué pour une raison inconnue."
            )

    def _refresh_job_controls(self):
        """
        Mission 100 section 6 ("UI"): Start is disabled outright when
        OneTrainer is not configured — checked here, not left to a
        failed launch attempt, with an actionable hint. Never a modal
        dialog just because the button is unavailable.
        """
        job_active = self._active_runner is not None
        has_selected_training = self.training_manager.active_training_id is not None

        try:
            resolve_onetrainer_launch(self.application_settings_manager.settings.onetrainer_path)
            onetrainer_configured = True
        except OneTrainerLaunchError:
            onetrainer_configured = False

        self.start_training_button.setEnabled(
            has_selected_training and not job_active and onetrainer_configured
        )
        self.cancel_training_button.setEnabled(job_active and not self._cancel_in_flight)

        if job_active:
            self.job_state_label.setText(
                "Annulation en cours…" if self._cancel_in_flight else "Entraînement en cours…"
            )
        elif not onetrainer_configured:
            self.job_state_label.setText(
                "Configurez OneTrainer dans Réglages avant de démarrer un entraînement."
            )
        else:
            self.job_state_label.setText("")

        self._refresh_jobs_list()

    def _refresh_jobs_list(self):
        """
        Mission 103: rebuilds the small Jobs list of the currently
        selected Training directly from Training.jobs — recomputed
        fresh on every call, never cached, so a Job's import status
        always reflects the real current state of the Central LoRA
        Library rather than a stale snapshot (MISSION_103.md section
        3.3). Selection is preserved across a rebuild by job_id, same
        convention as update_trainings() above for training_list.
        """
        previous_job_id = None
        current_item = self.jobs_list.currentItem()
        if current_item is not None:
            previous_job_id = current_item.data(Qt.UserRole)

        self.jobs_list.blockSignals(True)
        self.jobs_list.clear()

        training = self.training_manager.active_training

        restored_item = None
        if training is not None:
            for job in training.jobs:
                item = QListWidgetItem(self._describe_job(job))
                item.setData(Qt.UserRole, job.job_id)
                self.jobs_list.addItem(item)
                if job.job_id == previous_job_id:
                    restored_item = item

        if restored_item is not None:
            self.jobs_list.setCurrentItem(restored_item)

        self.jobs_list.blockSignals(False)

        self._refresh_import_button_state()

    def _describe_job(self, job) -> str:
        """
        Mission 103 section 3.3: the four import states, computed fresh
        — never a cached boolean — from the Job's own fields and a
        fresh read of the Central LoRA Library.
        """
        timestamp = (
            datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d %H:%M")
            if job.created_at
            else "?"
        )
        status = f"{timestamp} — {job.state}"

        if job.state != TRAINING_JOB_STATE_SUCCEEDED:
            return status

        if not job.final_output_path or not Path(job.final_output_path).is_file():
            return f"{status} — fichier introuvable"

        if not job.imported_lora_id:
            return f"{status} — importable"

        lora = self.lora_library_manager.get(job.imported_lora_id)
        if lora is not None:
            return f"{status} — importé : {lora.name}"

        return f"{status} — LoRA supprimé, réimport possible"

    def _on_job_selection_changed(self, current, previous):
        self._refresh_import_button_state()

    def _refresh_import_button_state(self):
        self.import_lora_button.setEnabled(self._importable_job() is not None)
        # Mission 109: recomputed from the same real data every time,
        # right alongside the import button — never a value cached at
        # import time, so a LoRA deleted afterwards correctly disables
        # this action again on the next selection/refresh.
        self.use_lora_in_inference_button.setEnabled(
            self._usable_in_inference_job() is not None
        )

    def _importable_job(self):
        """
        Mission 103: the single Job (if any) the currently selected row
        of jobs_list may be imported from — None disables the import
        action entirely. Reused as-is by import_selected_job_to_library()
        so the enable check and the actual action never disagree.
        """
        item = self.jobs_list.currentItem()
        if item is None:
            return None

        training = self.training_manager.active_training
        if training is None:
            return None

        job_id = item.data(Qt.UserRole)
        job = next((j for j in training.jobs if j.job_id == job_id), None)

        if job is None or job.state != TRAINING_JOB_STATE_SUCCEEDED:
            return None

        if not job.final_output_path or not Path(job.final_output_path).is_file():
            return None

        if job.imported_lora_id and self.lora_library_manager.get(job.imported_lora_id) is not None:
            return None

        return job

    def _usable_in_inference_job(self):
        """
        Mission 109: the single Job (if any) the currently selected row
        of jobs_list may be sent to Inference for — symmetric to
        _importable_job() above, but the opposite condition: a real
        imported_lora_id that still resolves to a real Central Library
        LoRA. Always re-read live (job.imported_lora_id then a fresh
        lora_library_manager.get() call) — never a boolean cached from
        the moment of import, so a LoRA deleted afterwards is reflected
        immediately on the next selection/refresh.
        """
        item = self.jobs_list.currentItem()
        if item is None:
            return None

        training = self.training_manager.active_training
        if training is None:
            return None

        job_id = item.data(Qt.UserRole)
        job = next((j for j in training.jobs if j.job_id == job_id), None)

        if job is None or not job.imported_lora_id:
            return None

        if self.lora_library_manager.get(job.imported_lora_id) is None:
            return None

        return job

    def use_selected_lora_in_inference(self):
        """
        Mission 109: emits use_lora_in_inference_requested(lora_id) for
        the Job returned by _usable_in_inference_job() — the same
        guard already used to enable/disable the button, so the click
        handler and the enable check never disagree (same discipline
        as import_selected_job_to_library()/_importable_job()). No
        navigation, no InferencePage/Sidebar reference here — MainWindow
        is the sole mediator, exactly like Prompts → Inference (Mission
        033).
        """
        job = self._usable_in_inference_job()
        if job is None:
            return

        self.use_lora_in_inference_requested.emit(job.imported_lora_id)

    def import_selected_job_to_library(self):
        """
        Mission 103 section 3.5: import_lora() first, then — only if it
        succeeds — set_job_imported_lora_id(). The Library entry created
        by a successful import_lora() is never rolled back if the
        second step fails: it is already real and already usable
        (LORA_LIBRARY_IMPORTED already published), so hiding or
        deleting it would be strictly worse than an honest partial-
        success message.
        """
        job = self._importable_job()
        if job is None:
            return

        training = self.training_manager.active_training
        if training is None:
            return

        # Never trust the stored final_output_path blindly — revalidate
        # right before the real copy, since the file could have been
        # removed since the list was last refreshed.
        if not Path(job.final_output_path).is_file():
            QMessageBox.warning(
                self,
                "Fichier introuvable",
                "Le fichier LoRA produit par cet entraînement est introuvable "
                f"({job.final_output_path}). Import annulé."
            )
            self._refresh_jobs_list()
            return

        name, ok = QInputDialog.getText(
            self,
            "Importer dans la Bibliothèque LoRA centrale",
            "Nom :",
            text=training.name,
        )

        if not ok or not name.strip():
            return

        try:
            library_root = resolve_lora_library_root(
                self.application_settings_manager.settings.lora_library_path
            )
        except LoRALibraryPathError as exc:
            QMessageBox.critical(self, "Erreur", str(exc))
            return

        try:
            lora = self.lora_library_manager.import_lora(
                name.strip(), [job.final_output_path], library_root=library_root,
                trigger_word=training.trigger_word,
            )
        except LoRALibraryError as exc:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'importer le LoRA dans la Bibliothèque centrale : {exc}"
            )
            return

        try:
            self.training_manager.set_job_imported_lora_id(job.job_id, lora.lora_id)
        except WorkspaceManagerError as exc:
            QMessageBox.warning(
                self,
                "Import partiel",
                f"Le LoRA « {lora.name} » a bien été importé dans la Bibliothèque "
                "centrale et est déjà utilisable, mais son association avec cet "
                f"entraînement n'a pas pu être enregistrée dans le projet : {exc}\n\n"
                "Cet entraînement réapparaîtra comme non importé — une nouvelle "
                "tentative d'import créera une entrée distincte dans la "
                "Bibliothèque, jamais un doublon fusionné automatiquement."
            )
            self._refresh_jobs_list()
            return

        QMessageBox.information(
            self,
            "Import réussi",
            f"Le LoRA « {lora.name} » a été importé dans la Bibliothèque LoRA centrale."
        )
        self._refresh_jobs_list()
