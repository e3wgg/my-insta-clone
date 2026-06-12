from flask import render_template_string
from flask_login import current_user
from models import Notification, Message


def get_layout(content_html, active_tab='', title='Instagram', dots_link=None):
    unread_notif_badge = ''
    unread_dm_badge    = ''
    try:
        if current_user.is_authenticated:
            notif_cnt = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).filter(Notification.notif_type.in_(['like', 'follow', 'comment'])).count()
            if notif_cnt > 0:
                unread_notif_badge = (
                    f'<span style="position:absolute;top:6px;right:6px;background:#e74c3c;'
                    f'color:white;border-radius:50%;width:16px;height:16px;display:flex;'
                    f'align-items:center;justify-content:center;font-size:9px;font-weight:700;">'
                    f'{notif_cnt if notif_cnt < 10 else "9+"}</span>'
                )
            dm_cnt = Message.query.filter_by(
                receiver_id=current_user.id, is_read=False
            ).count()
            if dm_cnt > 0:
                unread_dm_badge = (
                    f'<span style="position:absolute;top:4px;right:0px;background:#e74c3c;'
                    f'color:white;border-radius:50%;min-width:16px;height:16px;padding:0 3px;'
                    f'display:flex;align-items:center;justify-content:center;font-size:9px;'
                    f'font-weight:700;line-height:1;">'
                    f'{dm_cnt if dm_cnt < 100 else "99+"}</span>'
                )
    except Exception:
        pass

    uname = current_user.username if current_user.is_authenticated else ''

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Oleo+Script&display=swap');
            body {{ background-color:#edeff1; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; color:#262626; }}
            .insta-header {{ background:linear-gradient(to bottom,#4a8db7,#2a6a96); border-bottom:1px solid #0f466f; box-shadow:0 1px 2px rgba(0,0,0,.2); }}
            .insta-logo-font {{ font-family:'Oleo Script',cursive; }}
            .v5-btn {{ background:linear-gradient(to bottom,#fff,#f4f4f4); border:1px solid #ccc; border-radius:3px; padding:5px 10px; font-weight:600; font-size:12px; color:#444; box-shadow:0 1px 1px rgba(0,0,0,.05); text-align:center; display:inline-block; }}
            .v5-btn-blue {{ background:linear-gradient(to bottom,#4f8fc4,#26679c); border-color:#1e527d; color:#fff; }}
            .feed-container {{ border-bottom:1px solid #d3d3d3; background:#fff; }}
        </style>
        <title>{title}</title>
    </head>
    <body class="pb-16 max-w-md mx-auto bg-[#edeff1] min-h-screen relative shadow-md">

        <header class="insta-header sticky top-0 z-50 text-white h-11 flex items-center justify-between px-3">
            {'<a href="javascript:history.back()" class="text-white text-base opacity-80"><i class="fa-solid fa-chevron-left"></i></a>' if active_tab == 'profile' and title != 'Instagram' else '<span style="width:28px;"></span>'}
            <span class="{'text-base font-bold uppercase tracking-wide' if active_tab == 'profile' and title != 'Instagram' else 'text-2xl insta-logo-font'} text-center flex-1">{title}</span>
            <div class="flex items-center justify-end" style="width:36px;">
                {dots_link if dots_link else (
                    '<a href="/settings" class="text-white text-base"><i class="fa-solid fa-ellipsis-vertical"></i></a>'
                    if active_tab == "profile" and title != "Instagram"
                    else f'<a href="/messages" class="text-white text-lg" style="position:relative;display:inline-flex;align-items:center;justify-content:center;"><i class="fa-regular fa-paper-plane"></i>{unread_dm_badge}</a>'
                )}
            </div>
        </header>

        <main class="w-full">
            {content_html}
        </main>

        <footer class="fixed bottom-0 left-0 right-0 z-50 max-w-md mx-auto"
                style="background:linear-gradient(to bottom,#3a3a3a,#1e1e1e);border-top:1px solid #111;height:52px;display:flex;align-items:center;justify-content:space-around;">
            <a href="/" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-solid fa-house" style="font-size:20px;color:{'#fff' if active_tab=='home' else '#888'};"></i>
            </a>
            <a href="/search" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-solid fa-magnifying-glass" style="font-size:20px;color:{'#fff' if active_tab=='search' else '#888'};"></i>
            </a>
            <a href="/create-post" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <div style="width:40px;height:40px;border-radius:8px;border:2px solid {'#fff' if active_tab=='add' else '#777'};display:flex;align-items:center;justify-content:center;">
                    <i class="fa-regular fa-circle" style="font-size:10px;color:{'#fff' if active_tab=='add' else '#777'};"></i>
                </div>
            </a>
            <a href="/notifications" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;position:relative;">
                <i class="fa-regular fa-heart" style="font-size:20px;color:{'#fff' if active_tab=='notifications' else '#888'};"></i>
                {unread_notif_badge}
            </a>
            <a href="/user/{uname}" style="display:flex;align-items:center;justify-content:center;width:52px;height:52px;">
                <i class="fa-regular fa-user" style="font-size:20px;color:{'#fff' if active_tab=='profile' else '#888'};"></i>
            </a>
        </footer>
    </body>
    </html>
    """
    return html
