import subprocess


def run_database_migrations() -> None:
    result = subprocess.run(
        ["alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)

        raise RuntimeError(
            "Échec de la migration de la base de données."
        )
