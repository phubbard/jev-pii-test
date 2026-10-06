"""Synthetic labeled corpus generator.

Produces two artifacts with exact ground truth:

* ``records.jsonl`` — free-text support tickets, structured log lines and flat JSON
  records, each with character-offset PII spans. About 30% of records carry no PII at
  all but do contain hard negatives (order ids, company names, version strings that look
  like IPs, business phone lines, role mailboxes, appointment dates, card last-4...).
* ``tables/`` — CSV tables whose columns are labeled with a PII category or NONE, some
  with obfuscated headers so the detector has to judge values rather than names.

Everything is built with Faker, so no real person's data is involved and the data can be
regenerated at any size from a seed.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from faker import Faker

from jev_pii.taxonomy import LABELS, NONE_LABEL

SLOT = re.compile(r"\{([A-Z_]+|neg:[a-z0-9_]+)\}")
DATE_FORMATS = ("%m/%d/%Y", "%B %-d, %Y", "%Y-%m-%d")


@dataclass
class Record:
    id: str
    format: str
    text: str
    spans: list[dict] = field(default_factory=list)

    @property
    def labels(self) -> list[str]:
        return sorted({s["label"] for s in self.spans})

    def to_json(self) -> dict:
        d = asdict(self)
        d["labels"] = self.labels
        d["has_pii"] = bool(self.spans)
        return d


class Builder:
    """Concatenates text while recording exact offsets of PII values."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.spans: list[dict] = []
        self.pos = 0

    def lit(self, s: str) -> None:
        self.parts.append(s)
        self.pos += len(s)

    def pii(self, value: str, label: str) -> None:
        self.spans.append({"start": self.pos, "end": self.pos + len(value), "label": label, "value": value})
        self.lit(value)

    def text(self) -> str:
        return "".join(self.parts)


class Gen:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)

    # ---- PII values -------------------------------------------------------------
    def person_name(self) -> str:
        name = f"{self.fake.first_name()} {self.fake.last_name()}"
        if self.rng.random() < 0.15:
            name = f"{self.rng.choice(['Mr.', 'Ms.', 'Dr.', 'Mrs.'])} {name}"
        return name

    def email(self) -> str:
        return self.fake.free_email()

    def phone(self) -> str:
        a, b, c = self.rng.randint(201, 989), self.rng.randint(200, 999), self.rng.randint(0, 9999)
        fmt = self.rng.choice(
            ["({a}) {b}-{c:04d}", "{a}-{b}-{c:04d}", "{a}.{b}.{c:04d}", "+1 {a} {b} {c:04d}", "{a}{b}{c:04d}", "1-{a}-{b}-{c:04d}"]
        )
        return fmt.format(a=a, b=b, c=c)

    def ssn(self) -> str:
        return self.fake.ssn()

    def credit_card(self) -> str:
        num = self.fake.credit_card_number()
        style = self.rng.random()
        if style < 0.4 and len(num) == 16:
            return " ".join(num[i : i + 4] for i in range(0, 16, 4))
        if style < 0.6 and len(num) == 16:
            return "-".join(num[i : i + 4] for i in range(0, 16, 4))
        return num

    def street_address(self) -> str:
        street = self.fake.street_address().replace("\n", " ")
        return f"{street}, {self.fake.city()}, {self.fake.state_abbr()} {self.fake.postcode()}"

    def _fmt_date(self, d: dt.date) -> str:
        return d.strftime(self.rng.choice(DATE_FORMATS))

    def dob(self) -> str:
        return self._fmt_date(self.fake.date_of_birth(minimum_age=18, maximum_age=90))

    def ip(self) -> str:
        return self.fake.ipv4_public()

    PII = {
        "PERSON_NAME": "person_name",
        "EMAIL": "email",
        "PHONE": "phone",
        "SSN": "ssn",
        "CREDIT_CARD": "credit_card",
        "STREET_ADDRESS": "street_address",
        "DATE_OF_BIRTH": "dob",
        "IP_ADDRESS": "ip",
    }

    def value(self, label: str) -> str:
        return _json_safe(getattr(self, self.PII[label])())

    # ---- hard negatives ---------------------------------------------------------
    def neg(self, kind: str) -> str:
        r = self.rng
        f = self.fake
        match kind:
            case "order_id":
                return f"ORD-{r.randint(100000, 9999999)}"
            case "tracking":
                return "1Z" + "".join(r.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ", k=16))
            case "company":
                return f.company()
            case "version":
                if r.random() < 0.6:
                    return f"{r.randint(1, 12)}.{r.randint(0, 20)}.{r.randint(0, 99)}.{r.randint(1, 9999)}"
                return f"{r.randint(1, 12)}.{r.randint(0, 20)}.{r.randint(0, 99)}"
            case "netmask":
                return r.choice(["255.255.255.0", "255.255.0.0", "255.255.254.0"])
            case "business_phone":
                return r.choice(["1-800-{b}-{c:04d}", "(800) {b}-{c:04d}", "800-{b}-{c:04d}", "1-888-{b}-{c:04d}"]).format(
                    b=r.randint(200, 999), c=r.randint(0, 9999)
                )
            case "role_email":
                return f"{r.choice(['support', 'billing', 'noreply', 'sales', 'help', 'info', 'orders'])}@{f.domain_name()}"
            case "city":
                return f"{f.city()}, {f.state_abbr()}"
            case "appt_date":
                d = dt.date(2025, 1, 1) + dt.timedelta(days=r.randint(0, 1000))
                return self._fmt_date(d)
            case "card_last4":
                return f"{r.randint(0, 9999):04d}"
            case "timestamp":
                d = dt.datetime(2026, 1, 1) + dt.timedelta(seconds=r.randint(0, 20_000_000))
                return d.strftime("%Y-%m-%dT%H:%M:%SZ")
            case "year":
                return str(r.randint(2012, 2026))
            case "case_number":
                return f"{r.randint(100, 999)}-{r.randint(10, 99)}-{r.randint(1000, 9999)}"
            case "amount":
                return f"${r.randint(5, 5000):,}.{r.randint(0, 99):02d}"
            case "user_id":
                return f"u{r.randint(10000, 999999)}"
            case "sku":
                return f"SKU-{r.randint(1000, 99999)}"
            case "product":
                return r.choice(
                    ["Aurora Desk Lamp", "Northwind Backpack", "Trailhead Water Bottle", "Summit Pro Headphones", "Harbor Wool Blanket", "Vertex Standing Desk"]
                )
            case "status":
                return r.choice(["shipped", "pending", "refunded", "active", "closed", "delivered"])
            case "small_int":
                return str(r.randint(3, 900))
            case "store_address":
                return self.street_address()
            case _:
                raise KeyError(kind)


def _json_safe(s: str) -> str:
    return s.replace('"', "'").replace("\\", "/").replace("\n", " ")


# ---- templates --------------------------------------------------------------------
TICKET_SUBJECTS = [
    "Subject: Order issue",
    "Subject: Login problem",
    "Subject: Billing question",
    "Subject: Address change",
    "Subject: Refund request",
    "Subject: Account verification",
]
TICKET_GREETINGS = ["Hi,", "Hello support,", "To whom it may concern,", "Hi team,"]
TICKET_PII = [
    "My name is {PERSON_NAME} and I've been a customer for years.",
    "You can reach me at {EMAIL} if you need anything else.",
    "Please call me on my cell, {PHONE}, after 5pm.",
    "The best number for me is {PHONE}.",
    "Ship the replacement to {STREET_ADDRESS}.",
    "I recently moved; my new address is {STREET_ADDRESS}.",
    "For identity verification: date of birth {DATE_OF_BIRTH}.",
    "I was born on {DATE_OF_BIRTH}, in case that helps locate my file.",
    "My social security number is {SSN}.",
    "The SSN on file should be {SSN}, not whatever you have.",
    "The card I used was {CREDIT_CARD}, expiring 09/28.",
    "Charge it to {CREDIT_CARD} like last time.",
    "I was logged in from {IP_ADDRESS} when the error happened.",
    "The account was accessed from {IP_ADDRESS}, which isn't me.",
    "My wife {PERSON_NAME} also has an account under {EMAIL}.",
    "Contact: {PERSON_NAME}, {PHONE}, {EMAIL}.",
]
TICKET_PLAIN = [
    "My order {neg:order_id} still hasn't arrived.",
    "Tracking shows {neg:tracking} stuck in transit since {neg:appt_date}.",
    "Our company, {neg:company}, has used your service since {neg:year}.",
    "The problem started after updating to version {neg:version}.",
    "I called your main line {neg:business_phone} twice and got nowhere.",
    "Please copy {neg:role_email} on the reply.",
    "I was charged {neg:amount} on the card ending in {neg:card_last4}.",
    "My appointment is scheduled for {neg:appt_date} at your {neg:city} location.",
    "Case number {neg:case_number} was opened last week.",
    "I bought the {neg:product} ({neg:sku}) during the sale.",
    "Your store at {neg:store_address} said to contact you directly.",
    "This is really frustrating and I'd like it resolved this week.",
    "The app crashes every time I open the settings page.",
    "Can someone confirm the refund has been processed?",
    "I've attached a screenshot of the error message.",
]
TICKET_SIGNOFF_PII = ["Thanks,\n{PERSON_NAME}", "Regards,\n{PERSON_NAME}"]
TICKET_SIGNOFF_PLAIN = ["Thanks!", "Regards", "Thanks in advance."]

LOG_PII = [
    "{neg:timestamp} INFO auth login_ok user={neg:user_id} ip={IP_ADDRESS}",
    "{neg:timestamp} WARN auth login_failed user={neg:user_id} ip={IP_ADDRESS} attempts=3",
    "{neg:timestamp} INFO mail password_reset_sent to={EMAIL}",
    '{neg:timestamp} INFO profile update user={neg:user_id} name="{PERSON_NAME}"',
    "{neg:timestamp} ERROR payments declined card={CREDIT_CARD} reason=insufficient_funds",
    "{neg:timestamp} INFO sms otp_sent to={PHONE}",
    "{neg:timestamp} INFO kyc verified user={neg:user_id} dob={DATE_OF_BIRTH}",
    "{neg:timestamp} INFO kyc ssn_submitted user={neg:user_id} ssn={SSN}",
    '{neg:timestamp} INFO shipping label_created to="{STREET_ADDRESS}"',
    '{neg:timestamp} INFO support ticket_opened by="{PERSON_NAME}" contact={EMAIL}',
]
LOG_PLAIN = [
    "{neg:timestamp} INFO deploy build={neg:version} status=ok",
    "{neg:timestamp} INFO orders shipped order={neg:order_id} tracking={neg:tracking}",
    "{neg:timestamp} DEBUG cache miss key=user:{neg:user_id}",
    "{neg:timestamp} INFO health ok latency_ms={neg:small_int}",
    "{neg:timestamp} INFO mail sent to={neg:role_email} template=invoice",
    "{neg:timestamp} INFO payments captured amount={neg:amount} card_last4={neg:card_last4}",
    "{neg:timestamp} WARN net netmask={neg:netmask} iface=eth0",
    "{neg:timestamp} INFO scheduler next_run={neg:appt_date}",
    "{neg:timestamp} INFO crm account={neg:company} plan=enterprise",
    "{neg:timestamp} INFO support ticket_closed case={neg:case_number}",
]

JSON_PII_FIELDS = [
    ("customer_name", "PERSON_NAME"),
    ("full_name", "PERSON_NAME"),
    ("email", "EMAIL"),
    ("contact_email", "EMAIL"),
    ("phone", "PHONE"),
    ("mobile", "PHONE"),
    ("address", "STREET_ADDRESS"),
    ("shipping_address", "STREET_ADDRESS"),
    ("dob", "DATE_OF_BIRTH"),
    ("date_of_birth", "DATE_OF_BIRTH"),
    ("ssn", "SSN"),
    ("tax_id", "SSN"),
    ("card_number", "CREDIT_CARD"),
    ("payment_method", "CREDIT_CARD"),
    ("last_ip", "IP_ADDRESS"),
    ("client_ip", "IP_ADDRESS"),
]
JSON_NEG_FIELDS = [
    ("order_id", "order_id"),
    ("company", "company"),
    ("app_version", "version"),
    ("support_contact", "role_email"),
    ("card_last4", "card_last4"),
    ("created_at", "timestamp"),
    ("status", "status"),
    ("amount", "amount"),
    ("tracking", "tracking"),
    ("appointment", "appt_date"),
    ("store_location", "city"),
    ("case_ref", "case_number"),
    ("sku", "sku"),
    ("user_id", "user_id"),
]

# Column pool for tables: (header, kind) where kind is a PII label or a negative kind.
TABLE_COLUMNS = JSON_PII_FIELDS + JSON_NEG_FIELDS + [("product", "product"), ("quantity", "small_int")]


def render(gen: Gen, template: str, b: Builder) -> None:
    pos = 0
    for m in SLOT.finditer(template):
        b.lit(template[pos : m.start()])
        slot = m.group(1)
        if slot.startswith("neg:"):
            b.lit(gen.neg(slot[4:]))
        else:
            b.pii(gen.value(slot), slot)
        pos = m.end()
    b.lit(template[pos:])


def _n_pii(rng: random.Random) -> int:
    return 0 if rng.random() < 0.3 else rng.randint(1, 3)


def make_ticket(gen: Gen, rid: str) -> Record:
    rng = gen.rng
    b = Builder()
    n = _n_pii(rng)
    pii = rng.sample(TICKET_PII, k=min(n, len(TICKET_PII))) if n else []
    plain = rng.sample(TICKET_PLAIN, k=rng.randint(1, 3))
    body = pii + plain
    rng.shuffle(body)
    render(gen, rng.choice(TICKET_SUBJECTS), b)
    b.lit("\n\n")
    b.lit(rng.choice(TICKET_GREETINGS))
    b.lit("\n\n")
    for i, sent in enumerate(body):
        render(gen, sent, b)
        b.lit(" " if i < len(body) - 1 else "")
    b.lit("\n\n")
    signoff = rng.choice(TICKET_SIGNOFF_PII) if (n and rng.random() < 0.6) else rng.choice(TICKET_SIGNOFF_PLAIN)
    render(gen, signoff, b)
    return Record(rid, "ticket", b.text(), b.spans)


def make_log(gen: Gen, rid: str) -> Record:
    rng = gen.rng
    b = Builder()
    n = _n_pii(rng)
    lines = rng.sample(LOG_PII, k=min(n, len(LOG_PII))) if n else []
    lines += rng.sample(LOG_PLAIN, k=rng.randint(1, 2))
    rng.shuffle(lines)
    for i, line in enumerate(lines):
        render(gen, line, b)
        if i < len(lines) - 1:
            b.lit("\n")
    return Record(rid, "log", b.text(), b.spans)


def make_json(gen: Gen, rid: str) -> Record:
    rng = gen.rng
    b = Builder()
    n = _n_pii(rng)
    fields: list[tuple[str, str, str | None]] = []
    for key, label in rng.sample(JSON_PII_FIELDS, k=min(n, len(JSON_PII_FIELDS))) if n else []:
        fields.append((key, gen.value(label), label))
    for key, kind in rng.sample(JSON_NEG_FIELDS, k=rng.randint(2, 4)):
        fields.append((key, _json_safe(gen.neg(kind)), None))
    if rng.random() < 0.3:
        # free-text notes field that may itself carry PII
        nb = Builder()
        render(gen, rng.choice(TICKET_PII if (n and rng.random() < 0.5) else TICKET_PLAIN), nb)
        fields.append(("notes", _json_safe(nb.text()), ("__notes__", nb.spans)))  # type: ignore[arg-type]
    rng.shuffle(fields)
    b.lit("{\n")
    for i, (key, value, label) in enumerate(fields):
        b.lit(f'  "{key}": "')
        if isinstance(label, tuple):  # notes with embedded spans
            base = b.pos
            b.lit(value)
            for s in label[1]:
                b.spans.append({**s, "start": base + s["start"], "end": base + s["end"]})
        elif label:
            b.pii(value, label)
        else:
            b.lit(value)
        b.lit('"')
        b.lit(",\n" if i < len(fields) - 1 else "\n")
    b.lit("}")
    rec = Record(rid, "json", b.text(), sorted(b.spans, key=lambda s: s["start"]))
    json.loads(rec.text)  # must be valid JSON
    return rec


MAKERS = {"ticket": (make_ticket, 0.5), "log": (make_log, 0.25), "json": (make_json, 0.25)}


def generate_records(n: int, seed: int) -> list[Record]:
    gen = Gen(seed)
    names = list(MAKERS)
    weights = [MAKERS[k][1] for k in names]
    out = []
    for i in range(n):
        fmt = gen.rng.choices(names, weights)[0]
        out.append(MAKERS[fmt][0](gen, f"r{i:05d}"))
    return out


@dataclass
class Table:
    name: str
    columns: list[dict]  # {"name", "label", "kind"}
    rows: list[list[str]]
    obfuscated: bool

    def csv_text(self) -> str:
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([c["name"] for c in self.columns])
        w.writerows(self.rows)
        return buf.getvalue()


def generate_tables(n: int, seed: int, rows: int = 25) -> list[Table]:
    gen = Gen(seed + 1_000_003)
    rng = gen.rng
    out = []
    for t in range(n):
        picks = rng.sample(TABLE_COLUMNS, k=rng.randint(4, 8))
        obf = rng.random() < 0.3
        cols = []
        for j, (header, kind) in enumerate(picks):
            label = kind if kind in LABELS else NONE_LABEL
            cols.append({"name": f"col_{j + 1}" if obf else header, "label": label, "kind": kind})
        data = []
        for _ in range(rows):
            data.append([gen.value(c["kind"]) if c["label"] != NONE_LABEL else gen.neg(c["kind"]) for c in cols])
        out.append(Table(f"t{t:03d}", cols, data, obf))
    return out


def write_corpus(out_dir: Path, records: list[Record], tables: list[Table]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "records.jsonl").open("w") as f:
        for r in records:
            f.write(json.dumps(r.to_json()) + "\n")
    tdir = out_dir / "tables"
    tdir.mkdir(exist_ok=True)
    for t in tables:
        (tdir / f"{t.name}.csv").write_text(t.csv_text())
        (tdir / f"{t.name}.schema.json").write_text(
            json.dumps({"name": t.name, "obfuscated": t.obfuscated, "columns": t.columns}, indent=2)
        )


def load_records(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def load_tables(tdir: Path) -> list[dict]:
    tables = []
    for schema in sorted(tdir.glob("*.schema.json")):
        meta = json.loads(schema.read_text())
        with (tdir / f"{meta['name']}.csv").open() as f:
            rows = list(csv.reader(f))
        meta["header"] = rows[0]
        meta["rows"] = rows[1:]
        tables.append(meta)
    return tables
