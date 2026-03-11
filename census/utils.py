from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def send_email(to, subject, template, context):
    # Avoid a crash if I select a farm with no known emails when sending a campaign
    if len(to) > 0:
        text_content = render_to_string(
            "census/mails/" + template + ".txt",
            context=context,
        )

        html_content = render_to_string(
            "census/mails/" + template + ".html",
            context=context,
        )

        cc = ["antoine.paris@uclouvain.be"]
        if to[0] == cc[0]:
            cc = None

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email="Antoine Paris <recensement@maraichage-wallonie.be>",
            to=to,
            bcc=cc,
        )

        email.attach_alternative(html_content, "text/html")
        email.send()