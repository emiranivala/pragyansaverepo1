# ---------------------------------------------------
# File Name: login.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

from pyrogram import filters, Client
from devgagan import app
import random
import os
import asyncio
import string
from devgagan.core.mongo import db
from devgagan.core.func import subscribe, chk_user
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))  # Editted ...

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
        
@app.on_message(filters.command("login"))
async def generate_session(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return

    user_id = message.chat.id   

    # Ask user to share contact
    contact_msg = await _.ask(user_id, "Please share your phone number by clicking the button below.",
                              reply_markup={"keyboard": [[{"text": "Share Contact", "request_contact": True}]], "resize_keyboard": True})
    contact = await _.wait_for_message(user_id, filters=filters.contact)

    if contact:
        phone_number = contact.contact.phone_number
        await message.reply(f"📲 Received phone number: {phone_number}")

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

        # Ask the user to enter the OTP with spaces
        otp_code_msg = await _.ask(user_id, "Please check for an OTP in your official Telegram account. "
                                             "Once received, enter the OTP in the following format: \nFor example, `1 2 3 4 5`.",
                                   filters=filters.text, timeout=600)
        if otp_code_msg:
            phone_code = otp_code_msg.text.replace(" ", "")  # Remove spaces
            if len(phone_code) != 5 or not phone_code.isdigit():
                await otp_code_msg.reply("❌ Invalid OTP format. Please enter a 5-digit OTP in the format: 1 2 3 4 5.")
                return

            try:
                await client.sign_in(phone_number, code.phone_code_hash, phone_code)
            except PhoneCodeInvalid:
                await otp_code_msg.reply('❌ Invalid OTP. Please restart the session.')
                return
            except PhoneCodeExpired:
                await otp_code_msg.reply('❌ Expired OTP. Please restart the session.')
                return

            # Handle two-step verification if enabled
            try:
                if await client.is_password_needed():
                    two_step_msg = await _.ask(user_id, 'Your account has two-step verification enabled. Please enter your password.',
                                               filters=filters.text, timeout=300)
                    password = two_step_msg.text if two_step_msg else None
                    if password:
                        await client.check_password(password)
                    else:
                        await two_step_msg.reply('❌ Password is required. Please restart the session.')
                        return
            except PasswordHashInvalid:
                await otp_code_msg.reply('❌ Invalid password. Please restart the session.')
                return

            # Export session string
            string_session = await client.export_session_string()
            await db.set_session(user_id, string_session)
            await client.disconnect()

            # Respond to the user
            await otp_code_msg.reply("✅ Login successful!")
        else:
            await message.reply('❌ OTP input timed out. Please restart the session.')
