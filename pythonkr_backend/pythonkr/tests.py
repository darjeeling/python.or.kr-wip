import pytest
from datetime import date, time, timedelta
from django.utils import timezone
from .models import PKEvent, PKEvents, PKHomePage


@pytest.mark.django_db
def test_example():
    assert 1 == 1


@pytest.mark.django_db
class TestPKEventModel:
    """Test PKEvent model fields and methods"""

    def test_event_has_required_fields(self):
        """Test that PKEvent has all required fields"""
        # This will fail initially as we haven't added the fields yet
        event = PKEvent()
        assert hasattr(event, 'event_startdate')
        assert hasattr(event, 'event_enddate')
        assert hasattr(event, 'time_from')
        assert hasattr(event, 'time_to')
        assert hasattr(event, 'location')
        assert hasattr(event, 'listed')
        assert hasattr(event, 'content')
        assert hasattr(event, 'external_homepage')

    def test_event_date_display_single_day(self):
        """Test date display for single-day events"""
        # Create parent pages
        from wagtail.models import Page
        root = Page.get_root_nodes().first()

        home = PKHomePage(title="Home", slug="home-single")
        root.add_child(instance=home)

        events_page = PKEvents(title="Events", slug="events-single")
        home.add_child(instance=events_page)

        # Create event
        event = PKEvent(
            title="Test Event",
            slug="test-event",
            event_startdate=date(2025, 11, 1)
        )
        events_page.add_child(instance=event)

        # Single day event should not be multiday
        assert not event.is_multiday

    def test_event_date_display_multiday(self):
        """Test date display for multi-day events"""
        from wagtail.models import Page
        root = Page.get_root_nodes().first()

        home = PKHomePage(title="Home", slug="home-multiday")
        root.add_child(instance=home)

        events_page = PKEvents(title="Events", slug="events-multiday")
        home.add_child(instance=events_page)

        event = PKEvent(
            title="Multi Day Event",
            slug="multi-day",
            event_startdate=date(2025, 11, 1),
            event_enddate=date(2025, 11, 3)
        )
        events_page.add_child(instance=event)

        assert event.is_multiday

    def test_event_listed_default_false(self):
        """Test that listed defaults to False"""
        from wagtail.models import Page
        root = Page.get_root_nodes().first()

        home = PKHomePage(title="Home", slug="home-listed")
        root.add_child(instance=home)

        events_page = PKEvents(title="Events", slug="events-listed")
        home.add_child(instance=events_page)

        event = PKEvent(
            title="Test Event",
            slug="test-event",
            event_startdate=date.today()
        )
        events_page.add_child(instance=event)

        assert event.listed == False


@pytest.mark.django_db
class TestPKEventsPage:
    """Test PKEvents list page functionality"""

    def test_events_page_filters_listed_only(self):
        """Test that only listed events appear in context"""
        # Create page hierarchy
        from wagtail.models import Page
        root = Page.get_root_nodes().first()

        home = PKHomePage(title="Home", slug="home-filters")
        root.add_child(instance=home)

        events_page = PKEvents(title="Events", slug="events-filters")
        home.add_child(instance=events_page)

        # Create listed event
        listed_event = PKEvent(
            title="Listed Event",
            slug="listed",
            event_startdate=date.today(),
            listed=True
        )
        events_page.add_child(instance=listed_event)

        # Create unlisted event
        unlisted_event = PKEvent(
            title="Unlisted Event",
            slug="unlisted",
            event_startdate=date.today(),
            listed=False
        )
        events_page.add_child(instance=unlisted_event)

        # Get context
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        context = events_page.get_context(request)

        # Should only include listed event
        events = list(context['events'])
        assert len(events) == 1
        assert events[0].title == "Listed Event"

    def test_events_ordered_by_date_descending(self):
        """Test that events are ordered by date (newest first)"""
        from wagtail.models import Page
        root = Page.get_root_nodes().first()

        home = PKHomePage(title="Home", slug="home-ordered")
        root.add_child(instance=home)

        events_page = PKEvents(title="Events", slug="events-ordered")
        home.add_child(instance=events_page)

        # Create events with different dates
        old_event = PKEvent(
            title="Old Event",
            slug="old",
            event_startdate=date.today() - timedelta(days=30),
            listed=True
        )
        events_page.add_child(instance=old_event)

        new_event = PKEvent(
            title="New Event",
            slug="new",
            event_startdate=date.today(),
            listed=True
        )
        events_page.add_child(instance=new_event)

        # Get context
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        context = events_page.get_context(request)

        events = list(context['events'])
        # Newest should be first
        assert events[0].title == "New Event"
        assert events[1].title == "Old Event"
