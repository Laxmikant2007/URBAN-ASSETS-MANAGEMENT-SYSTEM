
from getpass import getpass
from pwdlib import PasswordHash
from database import get_db_connection

password_hash = PasswordHash.recommended()

ACCOUNTS = [
    (11, "Rohan Verma", "Admin"),
    (12, "Divya Nair", "Citizen"),
    (13, "Manoj Gowda", "Citizen"),
    (14, "Pooja Hegde", "Citizen"),
    (15, "Sanjay Rao", "Citizen"),
    (16, "Neha Joshi", "Citizen"),
    (17, "Ajay Kumar", "Citizen"),
    (18, "Kavya Reddy", "Citizen"),
    (19, "Nikhil Patil", "Citizen"),
    (20, "Asha Devi", "Citizen"),
]


def main():
    prepared = []

    print("Set new demo passwords.")
    print("Your passwords will not appear while typing.\n")

    for user_id, name, role in ACCOUNTS:
        while True:
            password = getpass(
                f"New password for {name} ({role}): "
            )
            confirm = getpass("Confirm password: ")

            if len(password) < 12:
                print("Use at least 12 characters.")
            elif password != confirm:
                print("Passwords do not match.")
            else:
                break

        prepared.append(
            (password_hash.hash(password), user_id)
        )
        del password, confirm

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Verify every account and its expected role first.
        for user_id, name, expected_role in ACCOUNTS:
            cursor.execute(
                "SELECT user_id, Role FROM `USER` "
                "WHERE user_id = %s",
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                raise RuntimeError(
                    f"Account {user_id} was not found."
                )

            if row["Role"] != expected_role:
                raise RuntimeError(
                    f"Unexpected role for {name}. "
                    f"Expected {expected_role}."
                )

        # Update password hashes only after all checks pass.
        for hashed_password, user_id in prepared:
            cursor.execute(
                """
                UPDATE `USER`
                SET PasswordHash = %s,
                    UpdatedAt = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """,
                (hashed_password, user_id),
            )

        connection.commit()
        print("\nSuccess: demo password hashes updated.")

    except Exception as error:
        if connection is not None and connection.is_connected():
            connection.rollback()

        print("\nNo password changes were committed.")
        print("Error:", error)

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
