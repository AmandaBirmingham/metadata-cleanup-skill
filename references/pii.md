# Personally identifiable information (PII) and protected health information (PHI)

Metadata about people is expected: most per-sample information about a human
subject (age, sex, diagnosis, medication) is information about that person,
and that is what the metadata is for. The problem is **personally identifiable
information (PII)** — information that identifies who the person is, alone or
in combination — and **protected health information (PHI)** as defined by
HIPAA (the 18 identifiers below). Do not flag ordinary subject metadata merely
because it describes a person.

No PII or PHI may be kept. Before any other review, the check script looks
for it by column name (S3-05) and by value pattern (S3-06) (SKILL.md, Phase
0). Everything else is read in the judgment review (`table_checks.md`),
where these lists guide what to look for but do not limit it.

If you find possible PII or PHI, tell the scientist plainly where it is and
why it may identify someone. How each finding is resolved is set out in
SKILL.md, Phase 0, and what follows when it is found later, in rule 12.

Initials can also be identifying.

## California (SB 1386, AB 1298)

A person's first name or first initial and last name, combined with any of:

- Social Security number;
- driver's license or California ID card number;
- financial account, credit card or debit card number (with any code or
  password that allows access);
- medical information (history, condition, treatment or diagnosis);
- health insurance information (policy number, subscriber ID, application and
  claims history);
- online account credentials: username or email address with a password or
  security question and answer (AB 370 / SB 46, effective 1 January 2014).

## HIPAA protected health information — 18 identifiers

1. Names.
2. Geographic data below state level: street address, city, county, ZIP code.
3. Dates related to a person: birth, admission, discharge, death; ages over 89.
4. Telephone numbers.
5. Fax numbers.
6. Email addresses.
7. Social Security numbers.
8. Medical record numbers.
9. Health plan beneficiary numbers.
10. Account numbers (financial, credit and debit cards).
11. Certificate and license numbers (passport, driver's license).
12. Vehicle identifiers, including license plates.
13. Device identifiers and serial numbers.
14. Web addresses (URLs).
15. IP addresses.
16. Biometrics (fingerprints, voice prints).
17. Full-face photographs and comparable images.
18. Any other unique identifying number, characteristic or code.

## Where to look

- Column names: patient_name, MRN, ssn, date_of_birth, dob, birthday, address,
  phone, email.
- Value patterns: `###-##-####`; 10-digit numbers; phone formats like
  (858) 534-2230; 6- or 8-digit numbers that could be dates; personal names.
- Unexpected places: identifying values pasted into unrelated columns (birth
  dates in a "zipcode" column).
