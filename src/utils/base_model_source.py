"""
Mission 106: Qt-free validation of Training.base_model_source, same
family and contract as src/utils/lora_library_path.py (Mission 104) —
a pure, stateless, filesystem-existence-only check shared by every
caller, never a moteur-specific concern (see MISSION_106.md section
3.1 for the full placement rationale).

base_model_source is deliberately opaque to this Domain (see
src/domain/training.py's own docstring) — a local .safetensors/.ckpt
file, a local Diffusers folder, or a Hugging Face identifier are all
legitimate values actually accepted by the installed OneTrainer
(confirmed by reading modules/modelLoader/stableDiffusion/
StableDiffusionModelLoader.py directly — MISSION_106.md section 1).
This module therefore rejects only the values Toolkit can be certain
no such form could ever resolve to: empty/whitespace-only, or a
Windows-absolute path (os.path.isabs() — a Hugging Face identifier
never carries a drive letter or a UNC prefix, so this discriminator is
never ambiguous, verified empirically for the exact forms this mission
audited) that does not exist as either a file or a directory. Anything
else — a relative string, an existing file, an existing directory, a
Hugging Face identifier — is passed through unchanged, never resolved,
never read, never contacted over the network.
"""
import os
from pathlib import Path


class InvalidBaseModelSourceError(Exception):
    """
    Raised by validate_base_model_source() only for a value no form
    accepted by OneTrainer could ever use — never for a value this
    module cannot be certain about (see this module's own docstring).
    """


def validate_base_model_source(base_model_source: str) -> None:
    stripped = base_model_source.strip()

    if not stripped:
        raise InvalidBaseModelSourceError(
            "Aucun modèle de base configuré. Renseignez un fichier checkpoint, "
            "un dossier Diffusers, ou un identifiant Hugging Face avant de "
            "préparer ou démarrer l'entraînement."
        )

    if os.path.isabs(stripped):
        path = Path(stripped)
        try:
            exists = path.is_file() or path.is_dir()
        except OSError:
            # An unreachable UNC host (WinError 64, "the specified
            # network name is no longer available") is not swallowed by
            # Path.is_file()/is_dir() into a plain False the way a
            # simple missing local file is — confirmed empirically
            # during this mission's own test run. Practically
            # equivalent to "does not exist" for this validation: an
            # unreachable absolute path is just as unusable by
            # OneTrainer as a missing one.
            exists = False
        if not exists:
            raise InvalidBaseModelSourceError(
                f"Le modèle de base est introuvable ou inaccessible : {stripped}. "
                "Vérifiez le chemin ou utilisez Parcourir."
            )
