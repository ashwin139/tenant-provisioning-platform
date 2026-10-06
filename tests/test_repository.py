"""State must survive a restart (new repository on the same file)."""
from app.models import Plan, Tenant, TenantModel
from app.repository import SqliteTenantRepository


def test_tenant_survives_restart(tmp_path):
    db = str(tmp_path / "t.db")
    t = Tenant(name="acme", region="ca-central-1", plan=Plan.STANDARD, tenant_model=TenantModel.POOLED)
    SqliteTenantRepository(db).add(t)
    reloaded = SqliteTenantRepository(db).get(t.tenant_id)
    assert reloaded is not None and reloaded.name == "acme"
