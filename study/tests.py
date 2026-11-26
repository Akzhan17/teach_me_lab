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

    def test_valid_demo_post_saves_source_and_three_flashcards(self):
        # DEMO режиміндегі нақты генерация функциясы орындалады.
        response = self.client.post(self.home_url, self.valid_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(Flashcard.objects.count(), 3)

        source = Source.objects.first()

        self.assertEqual(source.title, "Computer Networks")
        self.assertEqual(source.text, DEMO_TEXT)
        self.assertEqual(source.generation_mode, "DEMO")

        cards = list(source.cards.all())

        self.assertEqual(
            [card.position for card in cards],
            [1, 2, 3],
        )

        self.assertEqual(
            [card.question for card in cards],
            [item["question"] for item in DEMO_CARDS],
        )

        for card, expected in zip(cards, DEMO_CARDS):
            self.assertEqual(card.answer, expected["answer"])
            self.assertEqual(
                card.source_quote,
                expected["source_quote"],
            )

    def test_short_text_does_not_call_provider(self):
        invalid_data = {
            "title": "Short source",
            "text": "Too short",
        }

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.home_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

        mock_generate.assert_not_called()

    def test_invalid_source_quote_rejects_entire_result(self):
        invalid_cards = copy.deepcopy(DEMO_CARDS)
        invalid_cards[0]["source_quote"] = (
            "This text is not in the source."
        )

        with self.assertRaises(GenerationError):
            validate_cards(invalid_cards, DEMO_TEXT)

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

    def test_generation_error_returns_bound_form_without_database_writes(self):
        with patch(
            "study.views.generate_cards",
            side_effect=GenerationError("Generation failed."),
        ) as mock_generate:
            response = self.client.post(self.home_url, self.valid_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)
        self.assertTrue(response.context["form"].errors)

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

        mock_generate.assert_called_once_with(DEMO_TEXT)

    def test_database_error_rolls_back_source_and_first_flashcard(self):
        original_bulk_create = Flashcard.objects.bulk_create

        def insert_one_then_fail(objects, *args, **kwargs):
            original_bulk_create(objects[:1], *args, **kwargs)
            raise DatabaseError("Simulated database error.")

        with (
            patch(
                "study.views.generate_cards",
                return_value=DEMO_CARDS,
            ) as mock_generate,
            patch(
                "study.views.Flashcard.objects.bulk_create",
                side_effect=insert_one_then_fail,
            ) as mock_bulk_create,
        ):
            response = self.client.post(self.home_url, self.valid_data)

        self.assertEqual(response.status_code, 200)

        # Транзакция сәтсіз болса, Source пен Flashcard сақталмауы керек.
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

        mock_generate.assert_called_once_with(DEMO_TEXT)
        mock_bulk_create.assert_called_once()

    def test_two_detail_get_requests_do_not_call_provider_or_change_database(self):
        source = Source.objects.create(
            title="Computer Networks",
            text=DEMO_TEXT,
            generation_mode="DEMO",
        )

        for position, item in enumerate(DEMO_CARDS, start=1):
            Flashcard.objects.create(
                source=source,
                position=position,
                question=item["question"],
                answer=item["answer"],
                source_quote=item["source_quote"],
            )

        detail_url = reverse("source_detail", args=[source.pk])

        initial_source_count = Source.objects.count()
        initial_card_count = Flashcard.objects.count()

        with patch("study.views.generate_cards") as mock_generate:
            first_response = self.client.get(detail_url)
            second_response = self.client.get(detail_url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(first_response.context["source"], source)
        self.assertEqual(second_response.context["source"], source)

        self.assertContains(first_response, "Жауапты көрсету")
        self.assertContains(second_response, "Жауапты көрсету")

        self.assertEqual(
            first_response.content.decode().count("Жауапты көрсету"),
            3,
        )

        self.assertEqual(
            second_response.content.decode().count("Жауапты көрсету"),
            3,
        )

        mock_generate.assert_not_called()

        self.assertEqual(Source.objects.count(), initial_source_count)
        self.assertEqual(Flashcard.objects.count(), initial_card_count)