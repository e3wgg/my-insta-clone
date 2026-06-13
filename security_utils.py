import requests
from flask import request

def verify_turnstile():
    # هذا هو المفتاح السري الذي حصلت عليه
    SECRET_KEY = "0x4AAAAAAADj_fRdeu276uL28EJQiOvzpw08w"
    
    # الحصول على التوكن من النموذج
    token = request.form.get('cf-turnstile-response')
    
    # إذا لم يرسل المستخدم التوكن (محاولة تلاعب)
    if not token:
        return False
    
    # إرسال طلب التحقق لـ Cloudflare
    response = requests.post(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        data={
            'secret': SECRET_KEY,
            'response': token,
            'remoteip': request.remote_addr # إرسال الـ IP لزيادة الدقة
        }
    )
    
    # إرجاع النتيجة (True إذا كان إنساناً، False إذا كان بوت)
    return response.json().get('success', False)