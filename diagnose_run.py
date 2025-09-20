import os, sys, traceback
from pathlib import Path

print("CWD:", Path().resolve())
print("Looking for training_pipeline.py:", (Path("training_pipeline.py").exists()))

try:
    import training_pipeline as tp
    print("Imported training_pipeline OK from:", tp.__file__)
except Exception as e:
    print("FAILED to import training_pipeline:", e)
    traceback.print_exc()
    sys.exit(2)

try:
    tp.load_env()
    print("ENV loaded from:", Path(tp.__file__).parent / ".env")
    print("OPENAI_API_KEY present?:", bool(os.environ.get("OPENAI_API_KEY")))
    print("TRAINING_MODEL:", os.environ.get("TRAINING_MODEL"))
    print("VAULT_PATH:", os.environ.get("VAULT_PATH"))
    vault = tp.env_checks()
    print("Vault OK:", vault)
except Exception as e:
    print("env_checks FAILED:", e)
    traceback.print_exc()
    sys.exit(2)

notes = tp.scan_learning_inputs(vault)
print("Notes found:", len(notes), "->", [p.name for p in notes[:3]])
print("QUIZ_DIR:", os.environ.get("QUIZ_DIR"))
print("All good: you can now run training_pipeline.py normally.")
