"""Single source of truth for the PII categories this POC generates and detects.

Every category carries the wording used to build Jev questions (definition, exclusions,
examples) so the generator's hard negatives and the detector's criteria stay aligned.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    label: str
    noun: str
    definition: str
    excludes: str
    examples_yes: tuple[str, ...]
    examples_no: tuple[str, ...]


CATEGORIES: dict[str, Category] = {
    c.label: c
    for c in [
        Category(
            label="PERSON_NAME",
            noun="a person's name",
            definition=(
                "The given name and/or family name of a specific individual such as a "
                "customer, employee or patient, optionally with a title."
            ),
            excludes=(
                "Company, brand, product, team, software or place names; role words such "
                "as 'the customer' or 'our agent'."
            ),
            examples_yes=("Maria Gonzalez", "Mr. Daniel Okafor", "Dr. J. Patel"),
            examples_no=("Acme Corporation", "Microsoft Teams", "Mount Rainier"),
        ),
        Category(
            label="EMAIL",
            noun="a personal email address",
            definition="An email address that belongs to a specific individual's mailbox.",
            excludes=(
                "Role, team or system mailboxes such as support@, billing@, noreply@ "
                "or sales@ at a company domain."
            ),
            examples_yes=("jane.doe84@gmail.com", "d.okafor@yahoo.com"),
            examples_no=("support@acme.com", "noreply@payments.example"),
        ),
        Category(
            label="PHONE",
            noun="a personal telephone number",
            definition=(
                "A telephone number that reaches a specific individual, such as a mobile "
                "or direct line."
            ),
            excludes=(
                "Toll-free or published business main lines such as 1-800 numbers, "
                "order, case or tracking numbers."
            ),
            examples_yes=("(415) 555-0134", "+1 415 555 0134"),
            examples_no=("1-800-555-0199", "ORD-4821937"),
        ),
        Category(
            label="SSN",
            noun="a US Social Security number",
            definition=(
                "A nine-digit US Social Security number, usually written as three, two "
                "and four digits separated by dashes."
            ),
            excludes=(
                "Case, order, account or tracking numbers, even when they have nine digits "
                "or a similar dashed format."
            ),
            examples_yes=("SSN 482-19-3310", "social security number is 123-45-6789"),
            examples_no=("case number 482-19-3310", "tracking 1Z48219A3310"),
        ),
        Category(
            label="CREDIT_CARD",
            noun="a full payment card number",
            definition="A complete 12 to 19 digit credit or debit card number.",
            excludes=(
                "Partial references such as 'card ending in 4242', order numbers, "
                "loyalty or account IDs."
            ),
            examples_yes=("4532 0151 1283 0366", "5425233430109903"),
            examples_no=("card ending in 4242", "order 4532015112830366X"),
        ),
        Category(
            label="STREET_ADDRESS",
            noun="a residential street address",
            definition=(
                "A street address, with a street number and name, where a specific "
                "individual lives or receives mail."
            ),
            excludes=(
                "Company office or store addresses, and bare city, state or country names."
            ),
            examples_yes=("742 Evergreen Terrace, Springfield, IL 62704",),
            examples_no=("our Portland store", "Chicago, IL"),
        ),
        Category(
            label="DATE_OF_BIRTH",
            noun="a person's date of birth",
            definition="A calendar date that is stated or clearly implied to be when a person was born.",
            excludes="Appointment, invoice, shipping, incident or any other kind of date.",
            examples_yes=("DOB 03/04/1987", "born on March 4, 1987"),
            examples_no=("appointment on 03/04/2026", "invoice dated March 4, 2026"),
        ),
        Category(
            label="IP_ADDRESS",
            noun="an IP address of a user's device or connection",
            definition="An IPv4 address attributed to a user, customer, device or login.",
            excludes="Software version numbers, subnet masks and other dotted numbers.",
            examples_yes=("logged in from 203.0.113.42",),
            examples_no=("version 10.0.19045.3086", "netmask 255.255.255.0"),
        ),
    ]
}

LABELS: tuple[str, ...] = tuple(CATEGORIES)
NONE_LABEL = "NONE"


def describe(label: str) -> str:
    """One-line human description used in reports."""
    c = CATEGORIES[label]
    return f"{label}: {c.noun}"
