from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from testimonials.models import Testimonial, TestimonialsIndexPage

# Initial testimonial data
INITIAL_TESTIMONIAL = {
    "author": "Oleg Trott, PHD",
    "author_slug": "oleg_trott",
    "author_url": "https://www.olegtrott.com",
    "pull_quote": [
        {
            "id": "4c6ac70f-fd45-4ab5-85d7-69a790c14515",
            "type": "md",
            "value": """> What I really liked about Boost was that the libraries are peer-reviewed, raising expectations about quality and security. And I don't think I encountered a single bug in any of the Boost libraries I used. My thanks to the developers!

\\- [Oleg Trott](https://www.olegtrott.com), PHD
<br>
Creator, [AutoDoc Vina](https://vina.scripps.edu/)""",
        }
    ],
    "title": "The use of Boost C++ libraries in drug discovery",
    "body": [
        {
            "id": "92af493a-144c-406c-acce-ac10ab865911",
            "type": "md",
            "value": """[AutoDock Vina](https://vina.scripps.edu/) is the most popular molecular docking program, with [40,000 citations](https://scholar.google.com/citations?user=4BD7MkgAAAAJ), as of this writing. It is used widely to look for treatments for various diseases from cardiovascular and infectious ones to cancer. I created AutoDock Vina back when I was a postdoc at The Scripps Research Institute. And Boost C++ libraries were of great help.

The mechanisms of action of various drugs are different in each case, but what they have in common is that the drug (typically a small molecule consisting of dozens of atoms) binds a huge molecule, like a protein (consisting of thousands of atoms). This binding is normally non-covalent (think "physics", not "chemistry"). It is also quite specific – the shape and other properties of the drug have to be complementary to the protein, not unlike a lock and key. This binding interferes with the normal operation of the protein in question, and this may have some desired biological effect.

Modeling this binding process computationally is challenging, but, if done well, it can predict which small molecules would be promising as drugs.

When I got hired by The Scripps Research Institute almost 20 years ago, they had already been developing a molecular docking program, which they called "AutoDock", for many years. AutoDock was being used widely, including in huge efforts like the IBM World Community Grid, where volunteers contributed their personal compute to do docking calculations. In one such project, AutoDock was being used to look for new anti-HIV drugs. I estimated that in that single project, millions of dollars were being spent just on electricity (a cost borne by the volunteers). So performance was important.

Initially, my plan was to contribute to AutoDock, but after a few weeks on the job, I realized that the best path forward would be to write a new docking program instead. I thought I could re-implement the same or equivalent algorithm in a fraction of the lines of code, using modern (at the time) C++, employing STL and Boost.

While I didn't get fired right away, I'll say this: If you set out to do something ambitious in academia, the clock starts ticking for you, because while you are busy working on your new high-effort and high-risk project, you are probably not publishing some low-effort and low-risk work that is encouraged in academia. And what if your project fails? Rather perilous for your career.

To make matters worse, during this rewrite, my ambitions grew much further. I was no longer content with just a rewrite and started experimenting with alternative algorithms and scoring functions. (The scoring function tells us which binding is better.) Long story short, after 1.5 years, I released a new docking program and called it "VINA" (short for "VINA Is Not AutoDock"). It was superior to AutoDock:

* It was roughly 60 times faster, when using a single thread (potentially saving many millions in electricity and compute)
* Additionally, it supported parallelism across multiple CPU cores seamlessly
* It was significantly more accurate in its binding pose predictions, on average
* It supported all major platforms directly (AutoDock required a Unix-like environment)
* The code was a few times smaller

Later, I was asked to change the name to "AutoDock Vina". "AutoDock" became a brand, rather than the name of a particular program. Sadly, this is causing confusion to this day. Many people think that "Vina" was a new version of old software, but it was brand-new and simpler code implementing a more complex algorithm.

Boost C++ libraries were quite useful to me in cutting down on the development time, which as I mentioned was important. In particular, I used

* Boost.Thread – it enabled parallelism in a platform-independent way
* Boost.Serialization – for object persistence
* Boost.Math – for quaternions, which are used to represent 3D rotations conveniently
(Boost.QVM would have been more appropriate, but I don't think it was part of Boost back then)
* Boost.ProgramOptions – for parsing command line options and configuration files, as well as to
display the help message
* Boost.Filesystem – for handling files in a platform-independent way
* Boost.PointerContainer – for containers of pointers to objects
* Boost.Array – for "vectors" of statically known length
* Boost.Optional – for objects that may or may not be there
* Boost.LexicalCast – for parsing numbers, mostly
* Boost.Random – for thread-safe random number generation
* Boost.Timer – to show the users a progress bar, while they are waiting for the results

Since then, some of these libraries made it into the C++ standard, I believe.

What I really liked about Boost was that the libraries are peer-reviewed, raising expectations about quality and security. And I don't think I encountered a single bug in any of the Boost libraries I used. My thanks to the developers!""",
        }
    ],
}


class Command(BaseCommand):
    help = "Load initial testimonials data"

    def handle(self, *args, **options):
        # Check if testimonials index page already exists
        if TestimonialsIndexPage.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Testimonials index page already exists. Skipping data load."
                )
            )
            return

        # Get the site root page (typically the homepage)
        try:
            site = Site.objects.get(is_default_site=True)
            root_page = site.root_page
        except Site.DoesNotExist:
            # Fallback to the root page if no site exists
            root_page = Page.objects.get(depth=1)

        # Create the testimonials index page
        self.stdout.write("Creating testimonials index page...")
        index_page = TestimonialsIndexPage(
            title="Testimonials",
            slug="testimonials",
            show_in_menus=False,
        )
        root_page.add_child(instance=index_page)
        index_page.save_revision().publish()
        self.stdout.write(
            self.style.SUCCESS(f"Created testimonials index page (ID: {index_page.id})")
        )

        # Create the initial testimonial
        self.stdout.write(
            f"Creating testimonial for {INITIAL_TESTIMONIAL['author']}..."
        )
        testimonial = Testimonial(
            title=INITIAL_TESTIMONIAL["title"],
            slug=INITIAL_TESTIMONIAL["author_slug"],
            author=INITIAL_TESTIMONIAL["author"],
            author_slug=INITIAL_TESTIMONIAL["author_slug"],
            author_url=INITIAL_TESTIMONIAL["author_url"],
            pull_quote=INITIAL_TESTIMONIAL["pull_quote"],
            body=INITIAL_TESTIMONIAL["body"],
            show_in_menus=False,
        )
        index_page.add_child(instance=testimonial)
        testimonial.save_revision().publish()
        self.stdout.write(
            self.style.SUCCESS(f"Created testimonial (ID: {testimonial.id})")
        )

        self.stdout.write(
            self.style.SUCCESS("\nSuccessfully loaded initial testimonials data!")
        )
