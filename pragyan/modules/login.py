from pyrogram import filters, Client
from pragyan import app
import random
import os
import asyncio
import string
from pragyan.core.mongo import db
from pragyan.core.func import subscribe, chk_user
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

    # user_checked = await chk_user(message, message.from_user.id)
    # if user_checked == 1:
        # return
        
    user_id = message.chat.id   

    # Custom method to wait for the user's message
    async def wait_for_message(client, user_id, timeout=60):
        try:
            message = await client.listen(filters.text & filters.user(user_id), timeout=timeout)
            return message
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout reached while waiting for the message.")

    try:
        # Wait for the phone number message from the user
        number_msg = await wait_for_message(_, user_id, timeout=60)
        phone_number = number_msg.text
        
        await message.reply("📲 Sending OTP...")

        client = Client(f"session_{user_id}", api_id, api_hash)
        await client.connect()
        
        # Send OTP to the phone number
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
        return
    except PhoneNumberInvalid:
        await message.reply('❌ Invalid phone number. Please restart the session.')
        return
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP: {e}")
        return

    try:
        # Wait for the OTP from the user
        otp_code_msg = await wait_for_message(_, user_id, timeout=600)
        otp_code = otp_code_msg.text.replace(" ", "")
        
        # Sign in the user using the OTP
        await client.sign_in(phone_number, code.phone_code_hash, otp_code)
                
    except PhoneCodeInvalid:
        await message.reply('❌ Invalid OTP. Please restart the session.')
        return
    except PhoneCodeExpired:
        await message.reply('❌ Expired OTP. Please restart the session.')
        return
    except SessionPasswordNeeded:
        try:
            two_step_msg = await wait_for_message(_, user_id, 'Your account has two-step verification enabled. Please enter your password.', timeout=300)
            password = two_step_msg.text
            await client.check_password(password=password)
        except PasswordHashInvalid:
            await two_step_msg.reply('❌ Invalid password. Please restart the session.')
            return
        except TimeoutError:
            await message.reply('⏰ Time limit of 5 minutes exceeded. Please restart the session.')
            return

    # Export session string and save to database
    string_session = await client.export_session_string()
    await db.set_session(user_id, string_session)
    
    await client.disconnect()
    
    await otp_code_msg.reply("✅ Login successful!")
