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
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup

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
    contact_response = await client.listen(user_id, filters=filters.contact)

    if not contact_response or not contact_response.contact:
        await message.reply("❌ No contact received. Please try again.")
        return

    phone_number = contact_response.contact.phone_number
    await message.reply(f"📲 Received phone number: {phone_number}")

    try:
        await message.reply("📲 Sending OTP...")

        # Create a new Client instance for each user to handle login independently
        client = Client(f"session_{user_id}", api_id, api_hash)
        await client.connect()

    except Exception as e:
        await message.reply(f"❌ Failed to send OTP: {e}. Please wait and try again later.")
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

    # Ask the user to enter the OTP with spaces
    await message.reply("Please enter the OTP you received in the following format: 1 2 3 4 5")
    
    try:
        otp_code_response = await client.listen(user_id, filters=filters.text, timeout=600)  # 10 minutes timeout
        if not otp_code_response:
            await message.reply('⏰ Time limit of 10 minutes exceeded. Please restart the session.')
            return
        phone_code = otp_code_response.text.replace(" ", "")  # Remove spaces
        
        # Validate OTP length (5 digits)
        if len(phone_code) != 5 or not phone_code.isdigit():
            await message.reply("❌ Invalid OTP format. Please enter a 5-digit OTP in the format: 1 2 3 4 5.")
            return

    except Exception:
        await message.reply('❌ Failed to capture OTP. Please try again.')
        return

    try:
        # Attempt to log in with the provided OTP
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ Expired OTP. Please restart the session.')
        return

    # If two-step verification is enabled
    try:
        if await client.is_password_needed():
            await message.reply("Your account has two-step verification enabled. Please enter your password.")
            password_response = await client.listen(
                user_id, filters=filters.text, timeout=300  # 5 minutes timeout
            )
            password = password_response.text if password_response else None
            if not password:
                await message.reply('❌ No password received. Please restart the session.')
                return
            
            await client.check_password(password)
    except PasswordHashInvalid:
        await message.reply('❌ Invalid password. Please restart the session.')
        return

    # Export session string
    string_session = await client.export_session_string()

    # Save session string to database
    await db.set_session(user_id, string_session)

    await client.disconnect()

    # Respond to the user
    await message.reply("✅ Login successful!")
