from dataclasses import dataclass

from werkzeug.security import check_password_hash, generate_password_hash

DEMO_PASSWORD = "demo123"


@dataclass(frozen=True)
class Employee:
    employee_id: str
    username: str
    password_hash: str
    display_name: str
    department: str
    email: str


def _hash(password: str) -> str:
    return generate_password_hash(password)


DEMO_EMPLOYEES: tuple[Employee, ...] = (
    Employee(
        employee_id="E1001",
        username="tanaka.hanako",
        password_hash=_hash(DEMO_PASSWORD),
        display_name="田中 花子",
        department="経理部",
        email="hanako.tanaka@kon-group.demo",
    ),
    Employee(
        employee_id="E2001",
        username="suzuki.taro",
        password_hash=_hash(DEMO_PASSWORD),
        display_name="鈴木 太郎",
        department="IT部",
        email="taro.suzuki@kon-group.demo",
    ),
    Employee(
        employee_id="E3001",
        username="yamada.yuki",
        password_hash=_hash(DEMO_PASSWORD),
        display_name="山田 由紀",
        department="人事部",
        email="yuki.yamada@kon-group.demo",
    ),
)


def find_employee_by_username(username: str) -> Employee | None:
    key = username.strip().lower()
    for emp in DEMO_EMPLOYEES:
        if emp.username.lower() == key:
            return emp
    return None


def find_employee_by_id(employee_id: str) -> Employee | None:
    key = employee_id.strip()
    for emp in DEMO_EMPLOYEES:
        if emp.employee_id == key:
            return emp
    return None


def verify_password(employee: Employee, password: str) -> bool:
    return check_password_hash(employee.password_hash, password)
