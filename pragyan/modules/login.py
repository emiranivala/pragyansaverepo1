from pyrogram import Client, filters
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
import random
import string
import os
from pragyan.core.mongo import db
from pragyan.core.func import subscribe

# Function to generate random name for session
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

# Logout function to clear session files
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
        await message.reply("✅ Logged out successfully.")

# Login function for handling user authentication and OTP
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

    # Send message asking user to share contact
    phone_number_msg = await message.reply(
        "Please share your contact number by clicking the button below.",
        reply_markup=reply_markup
    )

    # Wait for the user to share their contact
    @app.on_message(filters.contact & filters.user(user_id))
    async def contact_handler(_, contact_msg):
        if contact_msg.contact:
            phone_number = contact_msg.contact.phone_number
            await message.reply(f"📲 Received phone number: {phone_number}")

            # Create a new Client instance for each user to handle login independently
            session_name = generate_random_name()  # generate a random session name
            client_instance = Client(session_name, api_id, api_hash)
            await client_instance.connect()

            # Attempt to send OTP to the provided phone number
            try:
                code = await client_instance.send_code(phone_number)
            except ApiIdInvalid:
                await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
                return
            except PhoneNumberInvalid:
                await message.reply('❌ Invalid phone number. Please restart the session.')
                return

            # Ask the user for the OTP
            otp_code_msg = await message.reply(
                "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: 1 2 3 4 5."
            )

            # Wait for the user to input the OTP via on_message event
            @app.on_message(filters.text & filters.user(user_id))
            async def otp_handler(_, otp_msg):
                phone_code = otp_msg.text.replace(" ", "")  # Remove spaces from OTP

                try:
                    # Attempt to log in with the provided OTP
                    await client_instance.sign_in(phone_number, code.phone_code_hash, phone_code)
                except PhoneCodeInvalid:
                    await otp_msg.reply('❌ Invalid OTP. Please restart the session.')
                    return
                except PhoneCodeExpired:
                    await otp_msg.reply('❌ Expired OTP. Please restart the session.')
                    return

                # Handle two-step verification if enabled
                try:
                    await client_instance.sign_in(phone_number, code.phone_code_hash, phone_code)
                except SessionPasswordNeeded:
                    # Request password if two-step verification is enabled
                    password_msg = await message.reply("Your account has two-step verification enabled. Please enter your password.")
                        
                    # Wait for the user to input the password
                    password_response = await app.listen(
                        user_id, filters=filters.text, timeout=300  # 5-minute timeout for password
                    )
                    if not password_response:
                        await password_msg.reply('⏰ Time limit exceeded. Please restart the session.')
                        return

                    # Attempt to verify the password
                    try:
                        password = password_response.text
                        await client_instance.check_password(password)
                        await password_msg.reply("✅ Password verified successfully!")
                    except PasswordHashInvalid:
                        await password_msg.reply('❌ Invalid password. Please restart the session.')
                        return

                # Export session string after successful login
                string_session = await client_instance.export_session_string()

                # Save session string to database
                await db.set_session(user_id, string_session)
                await client_instance.disconnect()

                # Final success message
                await otp_msg.reply("✅ Login successful!")
