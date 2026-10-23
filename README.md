# Smart Campus Resource Booking System

This project demonstrates Tkinter GUI, SQLite persistence, lists/dictionaries, classes and inheritance, role-based screens, validation, booking policies and reports.

## 1. Requirements
- Python 3.10 or newer recommended
- Tkinter (usually included with standard Python on Windows/macOS; some Linux systems install it separately)
- No third-party Python packages are required.

## 2. Run the application
1. Extract the ZIP folder.
2. Open a terminal/Command Prompt in the extracted folder.
3. Run `python main.py` (on some systems use `python3 main.py`).
4. The first run creates `campus_booking.db` automatically in the same folder.
5. Log in with one of the demo accounts below.

## 3. Demo accounts
| Role | Username | Password |
|---|---|---|
| Lecturer | `lecturer` | `lecturer123` |
| Campus Administrator | `admin` | `admin123` |
| System Operator | `operator` | `operator123` |

These are demonstration credentials only. The program stores password hashes, but SHA-256 without a password-specific salt is not appropriate for a production authentication system.

## 4. Main features
- Lecturer registration and login
- Role-based screens for Lecturer, Campus Administrator and System Operator
- Three campuses with separate booking policies:
  - Johannesburg: maximum 4 hours, 08:00–18:00
  - Durban: maximum 3 hours, 09:00–17:00
  - Cape Town: maximum 2 hours, 08:00–16:00
- Resource listing and registration; resource codes must be unique
- Bookings stored in SQLite and linked to lecturer, campus and resource
- Overlap detection for the same resource
- View and cancel future bookings
- Campus administrator resource management and campus booking view
- System operator cross-campus booking view and usage reports

## 5. How to test
1. Log in as `lecturer / lecturer123`.
2. In **Book a resource**, use a future date such as `2027-01-15`, time `10:00`, duration `1`, and confirm.
3. Open **My bookings** to see the saved booking. Select a future active booking and cancel it.
4. Try to book the same resource for an overlapping time. The app should reject the second booking.
5. Log out and log in as `admin / admin123` to add a resource or view campus bookings.
6. Log out and log in as `operator / operator123` to compare all campuses in **Reports**.

## 6. Project structure
- `main.py` — all application code; comments explain the main steps.
- `README.md` — setup, features and testing instructions.
- `ASSIGNMENT_GUIDE.md` — suggested implementation and demonstration plan.
- `EXPECTED_OUTPUT.md` — text preview of the expected screens.
- `requirements.txt` — confirms that no external packages are required.

## 7. Important notes / limitations
- This is a learning/demo implementation, not a production system.
- Campus administrators are assigned to Johannesburg in the seeded demo account; this can be adjusted in the database or by extending registration/admin setup.
- The policy time check uses whole-hour durations and 24-hour time.
- Usage reports are based on booking records currently in the database; sample data starts with resources but no bookings.
- For a real deployment, use a stronger password-hashing method, audit logging, robust time-zone handling, and tests.

