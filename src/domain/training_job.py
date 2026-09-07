from dataclasses import dataclass


@dataclass
class TrainingJob:
    """
    Mission 100: a single real execution attempt of a Training. Ownership
    is implicit via Training.jobs — a Training can have zero, one, or
    several TrainingJob entries (one per Start click), never shared
    between them (see MISSION_100.md section 5/9).
    """

    job_id: str = ""

    # One of TrainingManager's TRAINING_JOB_STATE_* constants — never
    # "prepared" (Prepare stays Training-scoped, outside this entity's
    # lifecycle entirely, see MISSION_100.md section 5.1/5.2).
    state: str = ""

    # Absolute path to this Job's own frozen copy of the OneTrainer
    # configuration, captured once at creation (Start) — a later Prepare
    # rewrites the Training-level onetrainer_config.json but never this
    # snapshot (MISSION_100.md section 5.1).
    config_snapshot_path: str = ""

    # Deterministic, known before the subprocess even starts — where the
    # final .safetensors will be written if this Job succeeds.
    expected_output_path: str = ""

    # Populated only once state == "succeeded" and the file's presence
    # at expected_output_path has actually been verified — never
    # inferred from expected_output_path alone (MISSION_100.md section
    # 5.2).
    final_output_path: str = ""

    # Epoch seconds (time.time()), 0.0 meaning "not set yet" — no prior
    # Domain object in this project persists a timestamp, so there is no
    # established string/format convention to match; a plain float
    # avoids any timezone reasoning and is trivially JSON-serializable.
    created_at: float = 0.0

    ended_at: float = 0.0

    # Populated only when state == "failed" — a human-readable summary
    # of the real cause (a native exit code, a QProcess error, ...),
    # never a generic message.
    error_message: str = ""

    # Reserved for Mission 101 (Central LoRA Library import) — never
    # populated by Mission 100.
    imported_lora_id: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "state": self.state,
            "config_snapshot_path": self.config_snapshot_path,
            "expected_output_path": self.expected_output_path,
            "final_output_path": self.final_output_path,
            "created_at": self.created_at,
            "ended_at": self.ended_at,
            "error_message": self.error_message,
            "imported_lora_id": self.imported_lora_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingJob":
        return cls(
            job_id=data.get("job_id", ""),
            state=data.get("state", ""),
            config_snapshot_path=data.get("config_snapshot_path", ""),
            expected_output_path=data.get("expected_output_path", ""),
            final_output_path=data.get("final_output_path", ""),
            created_at=data.get("created_at", 0.0),
            ended_at=data.get("ended_at", 0.0),
            error_message=data.get("error_message", ""),
            imported_lora_id=data.get("imported_lora_id", ""),
        )
