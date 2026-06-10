"""
seed_hr.py — Synthetic HR dataset for the QueryLens demo PostgreSQL connection.

Relational by design (the contrast to the MongoDB e-commerce demo): six tables
joined by foreign keys — offices, departments, employees (self-referencing
manager), projects, assignments (M:N), salary_history.

Usage:
  python seed/seed_hr.py --uri postgresql://querylens:querylens@localhost:5432 --db demo_hr --drop
"""

import argparse
import random
import sys
from datetime import date, timedelta

import psycopg

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NUM_EMPLOYEES = 300
NUM_PROJECTS = 40

OFFICES = [
    ("Athens", "Greece"), ("Berlin", "Germany"), ("London", "United Kingdom"),
    ("New York", "United States"), ("Tokyo", "Japan"),
]
DEPARTMENTS = [
    ("Engineering", 0.42), ("Sales", 0.16), ("Marketing", 0.10), ("Finance", 0.08),
    ("Human Resources", 0.06), ("Customer Support", 0.12), ("Legal", 0.03), ("Operations", 0.03),
]
TITLES = {
    "Engineering": [("Software Engineer", 52000, 78000), ("Senior Software Engineer", 75000, 105000),
                    ("Staff Engineer", 100000, 135000), ("QA Engineer", 45000, 65000),
                    ("DevOps Engineer", 60000, 95000), ("Data Scientist", 65000, 100000)],
    "Sales": [("Account Executive", 40000, 70000), ("Sales Manager", 65000, 95000),
              ("Sales Development Rep", 32000, 48000)],
    "Marketing": [("Marketing Specialist", 38000, 55000), ("Content Manager", 45000, 65000),
                  ("Growth Manager", 55000, 80000)],
    "Finance": [("Accountant", 40000, 60000), ("Financial Analyst", 50000, 75000),
                ("Controller", 70000, 100000)],
    "Human Resources": [("HR Generalist", 38000, 55000), ("Recruiter", 40000, 60000),
                        ("HR Manager", 60000, 85000)],
    "Customer Support": [("Support Specialist", 30000, 45000), ("Support Team Lead", 45000, 62000)],
    "Legal": [("Legal Counsel", 70000, 110000), ("Paralegal", 40000, 58000)],
    "Operations": [("Operations Analyst", 42000, 62000), ("Office Manager", 38000, 55000)],
}
PROJECT_ADJ = ["Phoenix", "Atlas", "Orion", "Nova", "Zephyr", "Titan", "Aurora", "Vector",
               "Cobalt", "Mercury", "Lighthouse", "Compass", "Summit", "Horizon", "Delta"]
PROJECT_NOUN = ["Migration", "Launch", "Redesign", "Rollout", "Integration", "Platform",
                "Pipeline", "Dashboard", "Expansion", "Automation"]
PROJECT_STATUSES = ["planning", "active", "on_hold", "completed", "cancelled"]
ASSIGNMENT_ROLES = ["lead", "contributor", "reviewer", "advisor"]
FIRST = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
         "David", "Elizabeth", "William", "Sofia", "Nikos", "Eleni", "Giorgos", "Maria",
         "Hans", "Ingrid", "Yuki", "Kenji", "Aiko", "Oliver", "Charlotte", "Lucas", "Emma",
         "Mateo", "Valentina", "Wei", "Priya", "Arjun", "Fatima", "Omar", "Zoe", "Leo"]
LAST = ["Smith", "Johnson", "Brown", "Taylor", "Anderson", "Papadopoulos", "Georgiou",
        "Nikolaou", "Mueller", "Schmidt", "Fischer", "Tanaka", "Watanabe", "Suzuki",
        "Garcia", "Martinez", "Silva", "Santos", "Kim", "Park", "Chen", "Wang", "Patel",
        "Singh", "Novak", "Kowalski", "Johansson", "Eriksson", "Rossi", "Ferrari"]

DDL = """
DROP TABLE IF EXISTS salary_history, assignments, projects, employees, departments, offices CASCADE;

CREATE TABLE offices (
    id          serial PRIMARY KEY,
    city        text NOT NULL,
    country     text NOT NULL,
    opened_on   date NOT NULL
);

CREATE TABLE departments (
    id          serial PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    budget      numeric(12,2) NOT NULL
);

CREATE TABLE employees (
    id            serial PRIMARY KEY,
    first_name    text NOT NULL,
    last_name     text NOT NULL,
    email         text NOT NULL UNIQUE,
    title         text NOT NULL,
    salary        numeric(10,2) NOT NULL,
    hire_date     date NOT NULL,
    is_active     boolean NOT NULL DEFAULT true,
    department_id integer NOT NULL REFERENCES departments(id),
    office_id     integer NOT NULL REFERENCES offices(id),
    manager_id    integer REFERENCES employees(id)
);

CREATE TABLE projects (
    id            serial PRIMARY KEY,
    name          text NOT NULL,
    status        text NOT NULL,
    budget        numeric(12,2) NOT NULL,
    started_on    date NOT NULL,
    ended_on      date,
    department_id integer NOT NULL REFERENCES departments(id)
);

CREATE TABLE assignments (
    employee_id   integer NOT NULL REFERENCES employees(id),
    project_id    integer NOT NULL REFERENCES projects(id),
    role          text NOT NULL,
    allocation    numeric(3,2) NOT NULL,
    PRIMARY KEY (employee_id, project_id)
);

CREATE TABLE salary_history (
    id            serial PRIMARY KEY,
    employee_id   integer NOT NULL REFERENCES employees(id),
    salary        numeric(10,2) NOT NULL,
    effective_on  date NOT NULL,
    reason        text NOT NULL
);
"""


def rdate(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="postgresql://querylens:querylens@localhost:5432")
    ap.add_argument("--db", default="demo_hr")
    ap.add_argument("--drop", action="store_true")  # kept for CLI symmetry; DDL always recreates
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    today = date(2026, 6, 1)
    print("=" * 60 + "\n  QueryLens — Demo HR Dataset (PostgreSQL)\n" + "=" * 60)

    with psycopg.connect(args.uri, dbname=args.db) as conn, conn.cursor() as cur:
        cur.execute(DDL)

        for city, country in OFFICES:
            cur.execute(
                "INSERT INTO offices (city, country, opened_on) VALUES (%s, %s, %s)",
                (city, country, rdate(date(2012, 1, 1), date(2022, 1, 1))),
            )
        for name, _ in DEPARTMENTS:
            cur.execute(
                "INSERT INTO departments (name, budget) VALUES (%s, %s)",
                (name, round(random.uniform(250_000, 4_000_000), 2)),
            )

        # Employees: managers first so reports can reference them
        dept_weights = [w for _, w in DEPARTMENTS]
        managers_by_dept: dict[int, list[int]] = {}
        emails = set()
        employees = []
        for i in range(NUM_EMPLOYEES):
            dept_id = random.choices(range(1, len(DEPARTMENTS) + 1), weights=dept_weights)[0]
            dept_name = DEPARTMENTS[dept_id - 1][0]
            title, lo, hi = random.choice(TITLES[dept_name])
            fn, ln = random.choice(FIRST), random.choice(LAST)
            email = f"{fn.lower()}.{ln.lower()}@querylens-demo.com"
            while email in emails:
                email = f"{fn.lower()}.{ln.lower()}{random.randint(2, 999)}@querylens-demo.com"
            emails.add(email)
            hire = rdate(date(2015, 1, 1), today - timedelta(days=30))
            salary = round(random.uniform(lo, hi), 2)
            manager_id = None
            if i >= 20 and managers_by_dept.get(dept_id):
                manager_id = random.choice(managers_by_dept[dept_id])
            cur.execute(
                "INSERT INTO employees (first_name, last_name, email, title, salary, hire_date,"
                " is_active, department_id, office_id, manager_id)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (fn, ln, email, title, salary, hire, random.random() > 0.07,
                 dept_id, random.randint(1, len(OFFICES)), manager_id),
            )
            emp_id = cur.fetchone()[0]
            employees.append((emp_id, salary, hire))
            if "Manager" in title or "Staff" in title or "Lead" in title or i < 20:
                managers_by_dept.setdefault(dept_id, []).append(emp_id)

        # Projects + assignments
        used_names = set()
        for _ in range(NUM_PROJECTS):
            name = f"{random.choice(PROJECT_ADJ)} {random.choice(PROJECT_NOUN)}"
            while name in used_names:
                name = f"{random.choice(PROJECT_ADJ)} {random.choice(PROJECT_NOUN)}"
            used_names.add(name)
            status = random.choices(PROJECT_STATUSES, weights=[10, 35, 10, 35, 10])[0]
            started = rdate(date(2022, 1, 1), today - timedelta(days=60))
            ended = rdate(started + timedelta(days=30), today) if status in ("completed", "cancelled") else None
            cur.execute(
                "INSERT INTO projects (name, status, budget, started_on, ended_on, department_id)"
                " VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (name, status, round(random.uniform(20_000, 900_000), 2), started, ended,
                 random.choices(range(1, len(DEPARTMENTS) + 1), weights=dept_weights)[0]),
            )
            project_id = cur.fetchone()[0]
            team = random.sample(employees, k=random.randint(3, 10))
            for j, (emp_id, _, _) in enumerate(team):
                cur.execute(
                    "INSERT INTO assignments (employee_id, project_id, role, allocation)"
                    " VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (emp_id, project_id, "lead" if j == 0 else random.choice(ASSIGNMENT_ROLES),
                     round(random.choice([0.25, 0.5, 0.75, 1.0]), 2)),
                )

        # Salary history: hire entry + 0-4 raises per employee
        n_history = 0
        for emp_id, salary, hire in employees:
            steps = random.randint(0, 4)
            current = salary / (1.06 ** steps)
            when = hire
            cur.execute(
                "INSERT INTO salary_history (employee_id, salary, effective_on, reason)"
                " VALUES (%s,%s,%s,%s)",
                (emp_id, round(current, 2), when, "hire"),
            )
            n_history += 1
            for _ in range(steps):
                current *= random.uniform(1.03, 1.12)
                when = rdate(min(when + timedelta(days=180), today), today)
                cur.execute(
                    "INSERT INTO salary_history (employee_id, salary, effective_on, reason)"
                    " VALUES (%s,%s,%s,%s)",
                    (emp_id, round(current, 2), when,
                     random.choice(["annual_review", "promotion", "market_adjustment"])),
                )
                n_history += 1

        conn.commit()
        for table in ("offices", "departments", "employees", "projects", "assignments", "salary_history"):
            cur.execute(f"SELECT count(*) FROM {table}")
            print(f"  {cur.fetchone()[0]:>6,} rows -> {table}")

    print("\nDone!")


if __name__ == "__main__":
    main()
