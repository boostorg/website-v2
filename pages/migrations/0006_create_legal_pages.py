import datetime

from django.db import migrations


PRIVACY_POLICY_BODY = """
<p>This privacy notice for The C Plus Plus Alliance, Inc. describes how and why we might collect, store, use, and/or share your information when you use our services ("Services").</p>
<p>The C Plus Plus Alliance is committed to protecting the privacy and accuracy of confidential information to the extent possible, subject to provisions of state and federal law. Other than as required by laws that guarantee public access to certain types of information, or in response to subpoenas or other legal instruments that authorize access, personal information is not actively shared.</p>
<p>In particular, we do not re-distribute or sell personal information collected on our web servers.</p>
<h2>Information collected</h2>
<p>The website collects the following analytics:</p>
<ul>
<li>Internet Protocol (IP) address of computer being used</li>
<li>web pages requested</li>
<li>referring web page</li>
<li>browser used</li>
<li>date and time</li>
</ul>
<p>We also collect any personal information that you voluntarily provide to us either while registering for an account or while using the site. This includes information such as your name, email address, and profile photo among other things.</p>
<p>We do not collect any sensitive information.</p>
<h2>Cookies</h2>
<p>The website may use cookies in order to deliver web content specific to individual users' interests or as functional cookies for the authentication purposes of the site. Sensitive personal information is not stored within cookies.</p>
<h2>Log and Usage Data</h2>
<p>We collect and store log and usage data for diagnostic and performance purposes. This may include the same analytics information above along with additional information related to your usage of the site.</p>
<h2>Privacy Statement Revisions</h2>
<p>We may update this privacy notice from time to time. The updated version will be indicated by an updated "Revised" date and the updated version will be effective as soon as it is accessible. If we make material changes to this privacy notice, we may notify you either by prominently posting a notice of such changes or by directly sending you a notification. We encourage you to review this privacy notice frequently to be informed of how we are protecting your information.</p>
<h2>Questions?</h2>
<p>Questions or concerns? Reading this privacy notice will help you understand your privacy rights and choices. If you do not agree with our policies and practices, please do not use our Services. If you still have any questions or concerns, please contact us at info@cppalliance.org.</p>
""".strip()


TERMS_OF_USE_BODY = """
<p>We are The C Plus Plus Alliance, Inc., a company registered in California, United States at 5716 Corsa Ave suite 110, Westlake Village, CA 91362, USA.</p>
<p>We operate this website, as well as any other related products and services that refer or link to these legal terms ("the Services").</p>
<p>These Legal Terms constitute a legally binding agreement made between you and The C Plus Plus Alliance, Inc., concerning your access to and use of the Services. You agree that by accessing the Services, you have read, understood, and agreed to be bound by all of these Legal Terms.</p>
<p>IF YOU DO NOT AGREE WITH ALL OF THESE LEGAL TERMS, THEN YOU ARE EXPRESSLY PROHIBITED FROM USING THE SERVICES AND YOU MUST DISCONTINUE USE IMMEDIATELY.</p>
<p>We reserve the right, in our sole discretion, to make changes or modifications to these Legal Terms from time to time. We will alert you about any changes by updating the "Last updated" date of these Legal Terms, and you waive any right to receive specific notice of each such change. It is your responsibility to periodically review these Legal Terms to stay informed of updates. You will be subject to, and will be deemed to have been made aware of and to have accepted, the changes in any revised Legal Terms by your continued use of the Services after the date such revised Legal Terms are posted.</p>
<p>We will make our best effort to notify registered users who have provided us with a valid email address of any changes to our Terms of Use via email. While we aim to ensure timely and accurate notifications, we do not guarantee that all changes will be communicated.</p>
<h2>Intellectual Property</h2>
<p>Boost libraries, documentation, source code, and this website are provided under the terms of the Boost Software License.</p>
<p>You grant The C Plus Plus Alliance, Inc. a royalty-free and non-exclusive license to display, use, copy, transmit, and broadcast the content you upload and publish. For issues regarding intellectual property claims, you should contact the The C Plus Plus Alliance, Inc.</p>
<h2>User Accounts</h2>
<p>As a user of this website you have the option, but not the requirement, to register with us and provide additional information. You are responsible for ensuring the accuracy of this information, and you are responsible for maintaining the safety and security of your identifying information.</p>
<p>You are also responsible for all activities that occur under your account or password.</p>
<p>If you think there are any possible issues regarding the security of your account on the website, inform us immediately so we may address them accordingly.</p>
<p>We reserve all rights to terminate accounts, edit or remove content and cancel orders at our sole discretion.</p>
<h2>Prohibited Activities</h2>
<p>As a user of the Services, you agree not to:</p>
<ul>
<li>Use any information obtained from the Services in order to harass, abuse, or harm another person.</li>
<li>Use the Services in a manner inconsistent with any applicable laws or regulations.</li>
<li>Attempt to impersonate another user or person or use the username of another user.</li>
<li>Interfere with, disrupt, or create an undue burden on the Services or the networks or services connected to the Services.</li>
<li>Harass, annoy, intimidate, or threaten any of our users, employees or agents engaged in providing any portion of the Services to you.</li>
<li>Attempt to bypass any measures of the Services designed to prevent or restrict access to the Services, or any portion of the Services.</li>
<li>Register another account after you have been terminated or suspended from the Services.</li>
</ul>
<p>In addition your contributions must meet these requirements:</p>
<ul>
<li>They are not obscene, lewd, lascivious, filthy, violent, harassing, libelous, slanderous, or otherwise objectionable (as determined by us).</li>
<li>They do not violate any applicable law, regulation, or rule.</li>
<li>They do not include any offensive comments including but not limited to race, national origin, gender, sexual preference, or physical handicap.</li>
<li>Your contributions must adhere to all relevant laws regarding child pornography and any which can or does result in the harming of a minor is strictly prohibited.</li>
</ul>
<h2>Third-Party Websites and Content</h2>
<p>The Services may contain links to other websites ("Third-Party Websites") as well as articles, photographs, text, graphics, pictures, designs, music, sound, video, information, applications, software, and other content or items belonging to or originating from third parties ("Third-Party Content"). Such Third-Party Websites and Third-Party Content are not investigated, monitored, or checked for accuracy, appropriateness, or completeness by us, and we are not responsible for any Third-Party Websites accessed through the Services or any Third-Party Content posted on, available through, or installed from the Services, including the content, accuracy, offensiveness, opinions, reliability, privacy practices, or other policies of or contained in the Third-Party Websites or the Third-Party Content.</p>
<h2>Modifications and Interruptions</h2>
<p>We reserve the right to change, modify, or remove the contents of the Services at any time or for any reason at our sole discretion without notice.</p>
<p>We cannot guarantee the Services will be available at all times. We may experience hardware, software, or other problems or need to perform maintenance related to the Services, resulting in interruptions, delays, or errors. We reserve the right to change, revise, update, suspend, discontinue, or otherwise modify the Services at any time or for any reason without notice to you.</p>
<h2>Governing Law</h2>
<p>These Legal Terms and your use of the Services are governed by and construed in accordance with the laws of the State of California applicable to agreements made and to be entirely performed within the State of California, without regard to its conflict of law principles.</p>
<h2>Disclaimer</h2>
<p>THE SERVICES ARE PROVIDED ON AN AS-IS AND AS-AVAILABLE BASIS. YOU AGREE THAT YOUR USE OF THE SERVICES WILL BE AT YOUR SOLE RISK. TO THE FULLEST EXTENT PERMITTED BY LAW, WE DISCLAIM ALL WARRANTIES, EXPRESS OR IMPLIED, IN CONNECTION WITH THE SERVICES AND YOUR USE THEREOF, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE MAKE NO WARRANTIES OR REPRESENTATIONS ABOUT THE ACCURACY OR COMPLETENESS OF THE SERVICES' CONTENT OR THE CONTENT OF ANY WEBSITES OR MOBILE APPLICATIONS LINKED TO THE SERVICES AND WE WILL ASSUME NO LIABILITY OR RESPONSIBILITY FOR ANY (1) ERRORS, MISTAKES, OR INACCURACIES OF CONTENT AND MATERIALS, (2) PERSONAL INJURY OR PROPERTY DAMAGE, OF ANY NATURE WHATSOEVER, RESULTING FROM YOUR ACCESS TO AND USE OF THE SERVICES, (3) ANY UNAUTHORIZED ACCESS TO OR USE OF OUR SECURE SERVERS AND/OR ANY AND ALL PERSONAL INFORMATION AND/OR FINANCIAL INFORMATION STORED THEREIN, (4) ANY INTERRUPTION OR CESSATION OF TRANSMISSION TO OR FROM THE SERVICES, (5) ANY BUGS, VIRUSES, TROJAN HORSES, OR THE LIKE WHICH MAY BE TRANSMITTED TO OR THROUGH THE SERVICES BY ANY THIRD PARTY, AND/OR (6) ANY ERRORS OR OMISSIONS IN ANY CONTENT AND MATERIALS OR FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF ANY CONTENT POSTED, TRANSMITTED, OR OTHERWISE MADE AVAILABLE VIA THE SERVICES. WE DO NOT WARRANT, ENDORSE, GUARANTEE, OR ASSUME RESPONSIBILITY FOR ANY PRODUCT OR SERVICE ADVERTISED OR OFFERED BY A THIRD PARTY THROUGH THE SERVICES, ANY HYPERLINKED WEBSITE, OR ANY WEBSITE OR MOBILE APPLICATION FEATURED IN ANY BANNER OR OTHER ADVERTISING, AND WE WILL NOT BE A PARTY TO OR IN ANY WAY BE RESPONSIBLE FOR MONITORING ANY TRANSACTION BETWEEN YOU AND ANY THIRD-PARTY PROVIDERS OF PRODUCTS OR SERVICES. AS WITH THE PURCHASE OF A PRODUCT OR SERVICE THROUGH ANY MEDIUM OR IN ANY ENVIRONMENT, YOU SHOULD USE YOUR BEST JUDGMENT AND EXERCISE CAUTION WHERE APPROPRIATE.</p>
<h2>CONTACT US</h2>
<p>In order to resolve a complaint regarding the Services or to receive further information regarding use of the Services, please contact us at:</p>
<p>The C Plus Plus Alliance, Inc. 5716 Corsa Ave suite 110 Westlake Village, CA 91362 United States</p>
<p>Phone: (+1)3052165538 info@cppalliance.org</p>
""".strip()


# Original publication dates on prod — keep revision history aligned.
LEGAL_PAGES = [
    {
        "title": "Privacy Policy",
        "slug": "privacy",
        "body": PRIVACY_POLICY_BODY,
        "last_updated": datetime.datetime(2024, 2, 17, tzinfo=datetime.timezone.utc),
    },
    {
        "title": "Terms of Use",
        "slug": "terms-of-use",
        "body": TERMS_OF_USE_BODY,
        "last_updated": datetime.datetime(2024, 2, 22, tzinfo=datetime.timezone.utc),
    },
]


def create_legal_pages(apps, schema_editor):
    # Use real models so treebeard's add_child() and Wagtail's
    # save_revision()/publish() work; historical models drop these methods.
    from pages.models import LegalPage, RoutableHomePage

    home = RoutableHomePage.objects.first()
    if home is None:
        return

    for page_data in LEGAL_PAGES:
        if LegalPage.objects.filter(slug=page_data["slug"]).exists():
            continue
        last_updated = page_data["last_updated"]
        page = home.add_child(
            instance=LegalPage(
                title=page_data["title"],
                slug=page_data["slug"],
                body=page_data["body"],
                live=True,
            )
        )
        revision = page.save_revision()
        revision.created_at = last_updated
        revision.save(update_fields=["created_at"])
        revision.publish()
        
        # publish() resets the page timestamps to now() — overwrite them.
        LegalPage.objects.filter(pk=page.pk).update(
            first_published_at=last_updated,
            last_published_at=last_updated,
            latest_revision_created_at=last_updated,
        )


def delete_legal_pages(apps, schema_editor):
    from pages.models import LegalPage

    LegalPage.objects.filter(slug__in=[p["slug"] for p in LEGAL_PAGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0005_legalpage"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_legal_pages, delete_legal_pages),
    ]
