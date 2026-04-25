from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_monorepo_directories_exist():
    assert (PROJECT_ROOT / "frontend").is_dir()
    assert (PROJECT_ROOT / "backend").is_dir()
    assert (PROJECT_ROOT / "shared" / "openapi").is_dir()
    assert (PROJECT_ROOT / "infra").is_dir()
    assert (PROJECT_ROOT / ".github" / "workflows").is_dir()


def test_docker_compose_exists():
    assert (PROJECT_ROOT / "docker-compose.yml").is_file()


def test_backend_app_structure():
    app_dir = PROJECT_ROOT / "backend" / "app"
    assert (app_dir / "__init__.py").is_file()
    assert (app_dir / "main.py").is_file()
    assert (app_dir / "core" / "config.py").is_file()
    assert (app_dir / "core" / "database.py").is_file()
    assert (app_dir / "tasks" / "celery_app.py").is_file()
    for subdir in ["api", "core", "models", "services", "tasks", "agents", "rag"]:
        assert (app_dir / subdir / "__init__.py").is_file()


def test_backend_alembic_configured():
    backend = PROJECT_ROOT / "backend"
    assert (backend / "alembic.ini").is_file()
    assert (backend / "alembic" / "env.py").is_file()


def test_ci_workflows_exist():
    workflows = PROJECT_ROOT / ".github" / "workflows"
    assert (workflows / "ci-frontend.yml").is_file()
    # ci-backend.yml + build-image.yml were merged into backend.yml on
    # 2026-04-26 to add a quality gate (build needs lint+tests, see TD-119).
    assert (workflows / "backend.yml").is_file()


def test_gitignore_exists():
    assert (PROJECT_ROOT / ".gitignore").is_file()


def test_created_at_index_migration_exists():
    versions_dir = PROJECT_ROOT / "backend" / "alembic" / "versions"
    matches = list(versions_dir.glob("*add_created_at_index*"))
    assert len(matches) == 1
