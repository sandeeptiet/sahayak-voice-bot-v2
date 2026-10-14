BEGIN;

UPDATE sahayak.profiles
SET
    phone_e164 = '+918860457783',
    phone_trusted_at = now(),
    phone_trusted_by = 'EMP001',
    phone_trust_method =
        'Owner confirmed consent for automated POC calls'
WHERE employee_code = 'EMP001'
  AND is_test = false
RETURNING employee_code, display_name, phone_e164,
          phone_trusted_at, phone_trusted_by;
