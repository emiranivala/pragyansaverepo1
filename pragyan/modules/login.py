from pyrogram import filters
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)
from pragyan.core.mongo import db
from pragyan.core.func import subscribe
from config import API_ID as api_id, API_HASH as api_hash
import random
import os
import string
from pyrogram import Client

# Function to generate random name (optional)
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Function to delete session files
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

# Logout handler to delete session and files
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

# Login handler to generate session and handle OTP
@app.on_message(filters.command("login"))
async def generate_session(client, message):
    # Check if the user is subscribed
    joined = await subscribe(client, message)
    if joined == 1:
        return

    user_id = message.chat.id

    # Ask user to share contact
    contact_button = KeyboardButton("Share Contact", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True)

    phone_number_msg = await message.reply(
        "Please share your contact number by clicking the button below.",
        reply_markup=reply_markup
    )

    # Wait for user to share the contact
    @app.on_message(filters.contact & filters.user(user_id))
    async def contact_handler(_, contact_msg):
        if contact_msg.contact:
            phone_number = contact_msg.contact.phone_number
            await message.reply(f"📲 Received phone number: {phone_number}")

            # Create a new Client instance for each user to handle login independently
            client_instance = Client(f"session_{user_id}", api_id, api_hash)
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

            # Ask user to input OTP
            otp_code_msg = await app.ask(user_id, 
                                          "Please check for an OTP in your official Telegram account. Once received, enter the OTP in the following format: \nIf the OTP is `12345`, please enter it as `1 2 3 4 5`.",
                                          filters=filters.text, timeout=600)

            # Validate OTP input
            phone_code = otp_code_msg.text.replace(" ", "")
            try:
                await client_instance.sign_in(phone_number, code.phone_code_hash, phone_code)
            except PhoneCodeInvalid:
                await otp_code_msg.reply('❌ Invalid OTP. Please restart the session.')
                return
            except PhoneCodeExpired:
                await otp_code_msg.reply('❌ OTP has expired. Please restart the session.')
                return

            # Handle two-step verification
            try:
                await client_instance.sign_in(phone_number, code.phone_code_hash, phone_code)
            except SessionPasswordNeeded:
                # Ask for the password if two-step verification is enabled
                password_msg = await app.ask(user_id, 
                                              'Your account has two-step verification enabled. Please enter your password.',
                                              filters=filters.text, timeout=300)
                password = password_msg.text

                try:
                    await client_instance.check_password(password=password)
                    await message.reply("✅ Password verified successfully!")
                except PasswordHashInvalid:
                    await password_msg.reply('❌ Invalid password. Please restart the session.')
                    return

            # Export session string after successful login
            string_session = await client_instance.export_session_string()

            # Save session string to the database
            await db.set_session(user_id, string_session)

            await client_instance.disconnect()

            # Inform user about successful login
            await otp_code_msg.reply("✅ Login successful!")
        else:
            await message.reply("❌ No valid contact received. Please try again.")
