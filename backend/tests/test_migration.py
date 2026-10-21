import subprocess
import pytest
import sys
import os

@pytest.fixture(scope="module")
def alembic_test_db():
    subprocess.run(["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "postgres", "-c", "DROP DATABASE IF EXISTS test_alembic_db;"], capture_output=True)
    subprocess.run(["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "postgres", "-c", "CREATE DATABASE test_alembic_db;"], capture_output=True)
    
    yield "postgresql://postgres:postgres@localhost:5432/test_alembic_db"
    
    subprocess.run(["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "postgres", "-c", "DROP DATABASE test_alembic_db;"], capture_output=True)

def test_migration_upgrade_downgrade_upgrade(alembic_test_db, monkeypatch):
    env = os.environ.copy()
    env["DATABASE_URL"] = alembic_test_db.replace("postgresql://", "postgresql+asyncpg://")
    
    # 1. Upgrade head
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert res.returncode == 0, f"Upgrade failed: {res.stderr}"
    
    def check_enum():
        check_res = subprocess.run(
            ["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "test_alembic_db", "-t", "-c", "SELECT typname FROM pg_type WHERE typname = 'cvstatus';"],
            capture_output=True, text=True
        )
        return "cvstatus" in check_res.stdout
    
    assert check_enum(), "Enum cvstatus should exist after upgrade"
    
    # 2. Downgrade base
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "base"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert res.returncode == 0, f"Downgrade failed: {res.stderr}"
    
    assert not check_enum(), "Enum cvstatus should be dropped after downgrade"
    
    # 3. Upgrade head again
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert res.returncode == 0, f"Second upgrade failed: {res.stderr}"
    
    assert check_enum(), "Enum cvstatus should exist after second upgrade"


def test_migration_downgrade_blocked_when_multiple_attempts(alembic_test_db):
    env = os.environ.copy()
    env["DATABASE_URL"] = alembic_test_db.replace("postgresql://", "postgresql+asyncpg://")

    # Ensure at head
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert res.returncode == 0

    # Insert test data: 1 CV, 1 JobApp, and 2 InterviewSessions (attempt 1 and 2)
    sql_seed = """
    INSERT INTO cv_documents (id, original_filename, storage_key, media_type, size_bytes, sha256, status, extracted_text)
    VALUES ('11111111-1111-1111-1111-111111111111', 'cv.pdf', 'k1', 'application/pdf', 10, 'sha', 'extracted', 'text');

    INSERT INTO job_applications (id, cv_document_id, target_role, job_description)
    VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'Backend Intern', 'JD');

    INSERT INTO interview_sessions (id, job_application_id, status, provider, model, prompt_version, schema_version, attempt_number)
    VALUES ('33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'completed', 'groq', 'llama', '1', '1', 1);

    INSERT INTO interview_sessions (id, job_application_id, status, provider, model, prompt_version, schema_version, attempt_number)
    VALUES ('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222', 'completed', 'groq', 'llama', '1', '1', 2);
    """
    subprocess.run(
        ["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "test_alembic_db", "-c", sql_seed],
        capture_output=True, text=True, check=True
    )

    # Downgrade to feae8be1dc16 first so we test feae8be1dc16 downgrade guard
    res_to_feae = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "feae8be1dc16"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert res_to_feae.returncode == 0

    # Attempt downgrade -1 from feae8be1dc16 must FAIL safely without data loss!
    downgrade_res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "-1"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert downgrade_res.returncode != 0, "Downgrade should fail when multiple attempts exist!"
    assert "Cannot downgrade: multiple interview sessions exist" in (downgrade_res.stderr + downgrade_res.stdout)

    # Confirm both sessions are still intact!
    count_res = subprocess.run(
        ["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "test_alembic_db", "-t", "-c",
         "SELECT count(*) FROM interview_sessions WHERE job_application_id = '22222222-2222-2222-2222-222222222222';"],
        capture_output=True, text=True, check=True
    )
    assert count_res.stdout.strip() == "2", "Data must not be lost or deleted during blocked downgrade!"

    # Delete attempt 2 to allow safe downgrade
    subprocess.run(
        ["docker", "exec", "interview_postgres", "psql", "-U", "postgres", "-d", "test_alembic_db", "-c",
         "DELETE FROM interview_sessions WHERE id = '44444444-4444-4444-4444-444444444444';"],
        capture_output=True, text=True, check=True
    )

    # Now downgrade succeeds
    safe_downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "-1"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert safe_downgrade.returncode == 0, f"Downgrade should succeed when single attempt exists: {safe_downgrade.stderr}"

    # Upgrade head back
    upgrade_back = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        env=env, cwd=os.path.join(os.path.dirname(__file__), "../../"), capture_output=True, text=True
    )
    assert upgrade_back.returncode == 0
