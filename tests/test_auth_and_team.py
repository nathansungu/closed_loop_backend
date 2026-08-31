import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.account import Account

client = TestClient(app)

def test_registration_creates_isolated_organization_and_requires_manual_login():
    email = f"test_org_admin_{uuid.uuid4().hex[:8]}@closedloop.io"
    org_name = f"Test Alpha Org {uuid.uuid4().hex[:6]}"
    
    # 1. Register new organization
    reg_res = client.post("/auth/register", json={
        "name": "Org Founder",
        "email": email,
        "password": "Password123!",
        "organization_name": org_name,
    })
    
    assert reg_res.status_code == 201, reg_res.text
    reg_data = reg_res.json()
    assert "access_token" not in reg_data, "Registration MUST NOT return access token (no auto-login)"
    assert reg_data["email"] == email
    assert reg_data["organization_name"] == org_name
    assert "Please log in" in reg_data["message"]

    # 2. Login explicitly with the registered credentials
    login_res = client.post("/auth/login", json={
        "email": email,
        "password": "Password123!",
    })
    assert login_res.status_code == 200, login_res.text
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]
    user_info = login_data["user"]
    assert user_info["role"] == "admin", "Organization creator must be assigned admin role"
    assert user_info["is_active"] is True
    assert user_info["organization_name"] == org_name
    account_id = user_info["account_id"]

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create a member under this organization
    member_email = f"member_{uuid.uuid4().hex[:8]}@closedloop.io"
    create_member_res = client.post("/users/", headers=headers, json={
        "name": "Team Member One",
        "email": member_email,
        "password": "MemberPass123!",
        "role": "member",
    })
    assert create_member_res.status_code == 201, create_member_res.text
    member_data = create_member_res.json()
    assert member_data["role"] == "member"
    assert member_data["account_id"] == account_id
    member_id = member_data["id"]

    # 4. Member logs in successfully
    member_login = client.post("/auth/login", json={
        "email": member_email,
        "password": "MemberPass123!",
    })
    assert member_login.status_code == 200

    # 5. Admin disables the member
    disable_res = client.patch(f"/users/{member_id}", headers=headers, json={
        "is_active": False,
    })
    assert disable_res.status_code == 200
    assert disable_res.json()["is_active"] is False

    # 6. Disabled member cannot log in
    disabled_login = client.post("/auth/login", json={
        "email": member_email,
        "password": "MemberPass123!",
    })
    assert disabled_login.status_code == 403, "Disabled user must be denied login with 403 Forbidden"
    assert "disabled" in disabled_login.json()["detail"].lower()

    # 7. Re-enable member and change role to viewer
    re_enable_res = client.patch(f"/users/{member_id}", headers=headers, json={
        "is_active": True,
        "role": "viewer",
    })
    assert re_enable_res.status_code == 200
    assert re_enable_res.json()["is_active"] is True
    assert re_enable_res.json()["role"] == "viewer"

    # 8. Viewer logs in and attempts to access GET /users/ -> Denied with 403 Forbidden
    viewer_login = client.post("/auth/login", json={
        "email": member_email,
        "password": "MemberPass123!",
    })
    assert viewer_login.status_code == 200
    viewer_token = viewer_login.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    viewer_list_res = client.get("/users/", headers=viewer_headers)
    assert viewer_list_res.status_code == 403, "Non-admin viewer must be denied access to team member management"


def test_duplicate_registration_returns_clear_detail_error():
    email = f"duplicate_test_{uuid.uuid4().hex[:8]}@closedloop.io"
    
    # 1. First registration succeeds
    reg1 = client.post("/auth/register", json={
        "name": "First User",
        "email": email,
        "password": "Password123!",
        "organization_name": "First Org",
    })
    assert reg1.status_code == 201

    # 2. Second registration with the same email returns clear error
    reg2 = client.post("/auth/register", json={
        "name": "Second User",
        "email": email,
        "password": "Password123!",
        "organization_name": "Second Org",
    })
    assert reg2.status_code == 400
    err_detail = reg2.json()["detail"]
    assert "Something is wrong with your details" in err_detail
    assert "already exists" in err_detail.lower()


def test_chama_creation_switching_and_renaming():
    admin_email = f"chama_boss_{uuid.uuid4().hex[:8]}@closedloop.io"
    
    # 1. Register & Login
    client.post("/auth/register", json={
        "name": "Chama Boss",
        "email": admin_email,
        "password": "BossPassword123!",
        "organization_name": "Initial Chama",
    })
    login_res = client.post("/auth/login", json={
        "email": admin_email,
        "password": "BossPassword123!",
    })
    token = login_res.json()["access_token"]
    initial_account_id = login_res.json()["user"]["account_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a new Chama under this user
    new_chama_res = client.post("/accounts/", headers=headers, json={
        "name": "Nairobi Horizon Chama",
    })
    assert new_chama_res.status_code == 201
    new_account_id = new_chama_res.json()["id"]
    assert new_chama_res.json()["name"] == "Nairobi Horizon Chama"

    # 3. List accounts - user should see both their initial Chama and new Chama
    list_res = client.get("/accounts/", headers=headers)
    assert list_res.status_code == 200
    acc_ids = [a["id"] for a in list_res.json()]
    assert initial_account_id in acc_ids
    assert new_account_id in acc_ids

    # 4. View participants in new empty Chama - returns [] (200 OK), NOT 403
    parts_res = client.get(f"/participants/account/{new_account_id}", headers=headers)
    assert parts_res.status_code == 200
    assert parts_res.json() == []

    # 5. Rename the new Chama
    rename_res = client.put(f"/accounts/{new_account_id}", headers=headers, json={
        "name": "Skyline Investment Chama",
    })
    assert rename_res.status_code == 200
    assert rename_res.json()["name"] == "Skyline Investment Chama"

    # 6. Switch back to initial Chama
    switch_res = client.post(f"/accounts/{initial_account_id}/switch", headers=headers)
    assert switch_res.status_code == 200
    assert switch_res.json()["id"] == initial_account_id

