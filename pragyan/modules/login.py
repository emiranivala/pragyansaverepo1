from pyrogram import Client, filters
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
async def generate_session(_, message):
    # Check subscription status
    joined = await subscribe(_, message)
    if joined == 1:
        return

    user_id = message.chat.id

    # Ask for phone number (using wait_for_message)
    phone_number_msg = await message.reply("Please enter your phone number along with the country code.\nExample: +19876543210")
    
    # Waiting for the message from the user using wait_for_message
    phone_number_response = await _.wait_for_message(user_id, filters=filters.text)

    phone_number = phone_number_response.text if phone_number_response else None

    if not phone_number:
        await message.reply("❌ No phone number received. Please try again.")
        return
    
    try:
        await message.reply("📲 Sending OTP...")

        # Create a new Client instance for each user to handle login independently
        client = Client(f"session_{user_id}", api_id, api_hash)
        await client.connect()

    except Exception as e:
        await message.reply(f"❌ Failed to send OTP {e}. Please wait and try again later.")
        return

    # Send OTP code to the phone number
    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number. Please restart the session.')
        return

    # Ask the user to enter the OTP
    await message.reply("Please enter the OTP you received (in the format: 5 4 7 2 3).")

    # Capture OTP input from the user
    @app.on_message(filters.text & filters.user(user_id))
    async def otp_handler(client, otp_msg):
        # Remove spaces from the OTP entered by the user
        phone_code = otp_msg.text.replace(" ", "")
        
        # Validate the OTP (check if it's 5 digits)
        if len(phone_code) != 5 or not phone_code.isdigit():
            await otp_msg.reply("❌ Invalid OTP format. Please enter a 5-digit OTP in the format: 5 4 7 2 3.")
            return

        try:
            # Sign in with the OTP
            await client.sign_in(phone_number, code.phone_code_hash, phone_code)
        except PhoneCodeInvalid:
            await otp_msg.reply('❌ Invalid OTP. Please restart the session.')
            return
        except PhoneCodeExpired:
            await otp_msg.reply('❌ Expired OTP. Please restart the session.')
            return

        # If two-step verification is enabled
        try:
            if await client.is_password_needed():
                await otp_msg.reply("Your account has two-step verification enabled. Please enter your password.")
                password_msg = await client.listen(user_id, filters=filters.text, timeout=300)
                password = password_msg.text if password_msg else None
                if not password:
                    await otp_msg.reply('❌ No password received. Please restart the session.')
                    return
                
                await client.check_password(password)
        except PasswordHashInvalid:
            await otp_msg.reply('❌ Invalid password. Please restart the session.')
            return

        # Export session string
        string_session = await client.export_session_string()
        
        # Save session string to database
        await db.set_session(user_id, string_session)
        
        await client.disconnect()

        # Respond to the user
        await otp_msg.reply("✅ Login successful!")
