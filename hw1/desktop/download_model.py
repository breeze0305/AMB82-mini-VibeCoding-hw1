"""Explicit one-time model download; runtime inference never accesses the cloud."""

from pathlib import Path

MODEL_REPO = "Systran/faster-whisper-small"
MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_NAME = "faster-whisper-small"
MODELS = Path(__file__).resolve().parent / "models"
REQUIRED = ("model.bin", "config.json", "tokenizer.json")


def main() -> None:
    target = MODELS / MODEL_NAME
    marker = target / ".model-revision"
    if (
        all((target / name).is_file() for name in REQUIRED)
        and marker.is_file()
        and marker.read_text(encoding="utf-8").strip() == MODEL_REVISION
    ):
        print(f"Whisper model already installed: {target}")
        return

    from huggingface_hub import snapshot_download

    print("Downloading multilingual Whisper small (about 500 MB), once only.", flush=True)
    # Public model, no login/token needed. Only model files are downloaded;
    # downloaded repository code is never executed.
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=str(target),
        allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"],
        token=False,
    )
    if not all((target / name).is_file() for name in REQUIRED):
        raise RuntimeError("Whisper model download is incomplete. Run setup.ps1 again.")
    marker.write_text(MODEL_REVISION + "\n", encoding="utf-8")
    print(f"Whisper model installed: {target}")


if __name__ == "__main__":
    main()
