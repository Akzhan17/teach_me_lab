
import copy

from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from .demo import DEMO_TEXT, DEMO_CARDS
from .models import Source, Flashcard
from .services import GenerationError, validate_cards


@override_settings(TEACHME_MODE="DEMO")
class StudyViewsTests(TestCase):

    def setUp(self):
        self.home_url = reverse("home")

        self.valid_data = {
            "title": "Computer Networks",
            "text": DEMO_TEXT,
        }

    @patch("study.services.urllib.request.urlopen")
    def test_valid_demo_post_saves_source_and_three_flashcards(
        self,
        mock_urlopen,
    ):
        self.assertEqual(len(DEMO_CARDS), 3)

        response = self.client.post(
            self.home_url,
            self.valid_data,
        )

        source = Source.objects.get()

        self.assertRedirects(
            response,
            reverse("source_detail", kwargs={"pk": source.pk}),
        )

        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(Flashcard.objects.count(), 3)

        self.assertEqual(source.title, "Computer Networks")
        self.assertEqual(source.text, DEMO_TEXT)
        self.assertEqual(source.generation_mode, "DEMO")

        cards = source.cards.order_by("position")

        self.assertEqual(
            list(cards.values_list("position", flat=True)),
            [1, 2, 3],
        )

        self.assertEqual(
            list(cards.values_list("question", flat=True)),
            [
                card["question"]
                for card in DEMO_CARDS
            ],
        )

        mock_urlopen.assert_not_called()

    @patch("study.views.generate_cards")
    @patch("study.services.urllib.request.urlopen")
    def test_short_text_does_not_call_provider(
        self,
        mock_urlopen,
        mock_generate_cards,
    ):
        response = self.client.post(
            self.home_url,
            {
                "title": "Short text",
                "text": "Too short.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        mock_generate_cards.assert_not_called()
        mock_urlopen.assert_not_called()

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

    def test_invalid_source_quote_rejects_entire_result(self):
        invalid_cards = copy.deepcopy(DEMO_CARDS)

        invalid_cards[1]["source_quote"] = (
            "This quotation does not exist in the study material."
        )

        payload = {
            "cards": invalid_cards,
        }

        with self.assertRaises(GenerationError):
            validate_cards(
                payload,
                DEMO_TEXT,
            )

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

    @patch("study.views.generate_cards")
    @patch("study.services.urllib.request.urlopen")
    def test_generation_error_returns_bound_form_without_database_writes(
        self,
        mock_urlopen,
        mock_generate_cards,
    ):
        mock_generate_cards.side_effect = GenerationError(
            "Gemini API request failed."
        )

        response = self.client.post(
            self.home_url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)

        self.assertEqual(
            response.context["form"]["title"].value(),
            "Computer Networks",
        )

        self.assertTrue(
            response.context["form"].non_field_errors()
        )

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

        mock_generate_cards.assert_called_once_with(DEMO_TEXT)
        mock_urlopen.assert_not_called()

    @patch("study.views.Flashcard.objects.bulk_create")
    @patch("study.views.generate_cards")
    @patch("study.services.urllib.request.urlopen")
    def test_database_error_rolls_back_source_and_first_flashcard(
        self,
        mock_urlopen,
        mock_generate_cards,
        mock_bulk_create,
    ):
        mock_generate_cards.return_value = copy.deepcopy(DEMO_CARDS)

        def insert_first_then_fail(objects, *args, **kwargs):
            # Use the real QuerySet method, not the patched Manager method.
            Flashcard.objects.get_queryset().bulk_create(
                objects[:1],
                *args,
                **kwargs,
            )

            raise DatabaseError(
                "Simulated database failure."
            )

        mock_bulk_create.side_effect = insert_first_then_fail

        response = self.client.post(
            self.home_url,
            self.valid_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)

        self.assertTrue(
            response.context["form"].non_field_errors()
        )

        # Both database writes must be rolled back.
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

        mock_generate_cards.assert_called_once_with(DEMO_TEXT)
        mock_bulk_create.assert_called_once()
        mock_urlopen.assert_not_called()

    @patch("study.views.generate_cards")
    @patch("study.services.urllib.request.urlopen")
    def test_two_detail_get_requests_do_not_call_provider_or_change_database(
        self,
        mock_urlopen,
        mock_generate_cards,
    ):
        source = Source.objects.create(
            title="Computer Networks",
            text=DEMO_TEXT,
            generation_mode="DEMO",
        )

        for position, card in enumerate(DEMO_CARDS, start=1):
            Flashcard.objects.create(
                source=source,
                position=position,
                question=card["question"],
                answer=card["answer"],
                source_quote=card["source_quote"],
            )

        detail_url = reverse(
            "source_detail",
            kwargs={"pk": source.pk},
        )

        initial_source_count = Source.objects.count()
        initial_card_count = Flashcard.objects.count()

        first_response = self.client.get(detail_url)
        second_response = self.client.get(detail_url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            first_response.context["source"].pk,
            source.pk,
        )

        self.assertEqual(
            second_response.context["source"].pk,
            source.pk,
        )

        self.assertContains(
            first_response,
            "Жауапты көрсету",
        )

        self.assertContains(
            second_response,
            "Жауапты көрсету",
        )

        mock_generate_cards.assert_not_called()
        mock_urlopen.assert_not_called()

        self.assertEqual(
            Source.objects.count(),
            initial_source_count,
        )

        self.assertEqual(
            Flashcard.objects.count(),
            initial_card_count,
        )
