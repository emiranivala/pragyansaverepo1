from pyrogram import Client, filters
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup
from pragyan import app
import random
import os
import string
from pragyan.core.mongo import db
from pragyan.core.func import subscribe
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)

# Function to generate random name
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Async function to delete session files
async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)
    
    if memory_file_exists:
        os.remove(memory_file)

    # Delete session from the database
    if session_file_exists or memory_file_exists:
        await db.remove_session(user_id)
        return True  # Files were deleted
    return False  # No files found

# Logout function to clear the database and session files
@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)
    try:
        await db.remove_session(user_id)
    except Exception:
        pass

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("✅ Logged out with flag -m")

# Login function for generating session
@app.on_message(filters.command("login"))
async def generate_session(client, message):
    # Check subscription status
    joined = await subscribe(client, message)
    if joined == 1:
        return

    user_id = message.chat.id

    # Ask the user to share their contact
    contact_button = KeyboardButton("Share Contact", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True)

    # Send a message asking the user to share their contact
    phone_number_msg = await message.reply(
        "Please share your contact number by clicking the button below.",
        reply_markup=reply_markup
    )

    # Wait for the user to share the contact
    @app.on_message(filters.contact & filters.user(user_id))
    async def contact_handler(_, contact_msg):
        if contact_msg.contact:
            phone_number = contact_msg.contact.phone_number
            await message.reply(f"📲 Received phone number: {phone_number}")

            # Create a new Client instance for each user to handle login independently
            client_instance = Client(f"session_{user_id}", api_id, api_hash)
            await client_instance.connect()

            # Check if two-step verification is needed
            try:
                if await client_instance.is_password_needed():
                    # Ask for the 2FA password if needed
                    await message.reply("Your account has two-step verification enabled. Please enter your password.")

                    # Wait for the user to input the password
                    password_response = await app.listen(
                        user_id, filters=filters.text, timeout=300  # 5 minutes timeout
                    )
                    
                    password = password_response.text if password_response else None
                    if not password:
                        await message.reply('❌ No password received. Please restart the session.')
                        return
                    
                    # Attempt to verify the password
                    await client_instance.check_password(password)
                    await message.reply("✅ Password verified successfully!")

            except PasswordHashInvalid:
                await message.reply('❌ Invalid password. Please restart the session.')
                return
            except SessionPasswordNeeded:
                await message.reply('❌ Failed to verify the password. Please restart the session.')
                return
            except Exception as e:
                await message.reply(f"❌ Error while verifying password: {str(e)}")
                return

            # Send OTP code to the phone number after password verification
            try:
                code = await client_instance.send_code(phone_number)
            except ApiIdInvalid:
                await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
                return
            except PhoneNumberInvalid:
                await message.reply('❌ Invalid phone number. Please restart the session.')
                return

            # Ask the user to enter the OTP with spaces
            await message.reply("Please enter the OTP you received in the following format: 7 3 5 2 4")

            @app.on_message(filters.text & filters.user(user_id))
            async def otp_handler(_, otp_code_msg):
                phone_code = otp_code_msg.text.replace(" ", "")  # Remove spaces
                
                # Validate OTP length (5 digits)
                if len(phone_code) != 5 or not phone_code.isdigit():
                    await otp_code_msg.reply("❌ Invalid OTP format. Please enter a 5-digit OTP in the format: 7 3 5 2 4.")
                    return

                try:
                    # Attempt to log in with the provided OTP
                    await client_instance.sign_in(phone_number, code.phone_code_hash, phone_code)
                except PhoneCodeInvalid:
                    await otp_code_msg.reply('❌ Invalid OTP. Please restart the session.')
                    return
                except PhoneCodeExpired:
                    await otp_code_msg.reply('❌ Expired OTP. Please restart the session.')
                    return

                # Export session string after successful login
                string_session = await client_instance.export_session_string()

                # Save session string to database
                await db.set_session(user_id, string_session)

                await client_instance.disconnect()

                # Respond to the user
                await otp_code_msg.reply("✅ Login successful!")
            return  # End the contact handler
        else:
            await message.reply("❌ No valid contact received. Please try again.")
