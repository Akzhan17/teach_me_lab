from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .demo import DEMO_TEXT, DEMO_CARDS
from .models import Source, Flashcard


@override_settings(TEACHME_MODE="DEMO")
class FlashcardEditorTests(TestCase):

    def setUp(self):
        self.source = Source.objects.create(
            title="Computer Networks",
            text=DEMO_TEXT,
            generation_mode="DEMO",
        )

        self.card1 = self.create_card(1)
        self.card2 = self.create_card(2)
        self.card3 = self.create_card(3)

        self.edit_url = reverse("card_edit", args=[self.card2.pk])
        self.delete_url = reverse("card_delete", args=[self.card2.pk])
        self.review_url = reverse("card_review", args=[self.card2.pk])
        self.detail_url = reverse("source_detail", args=[self.source.pk])

        self.valid_edit_data = {
            "question": "What is a computer network?",
            "answer": "A computer network connects devices.",
            "source_quote": DEMO_CARDS[0]["source_quote"],
        }

    def create_card(self, position):
        item = DEMO_CARDS[position - 1]

        return Flashcard.objects.create(
            source=self.source,
            position=position,
            question=item["question"],
            answer=item["answer"],
            source_quote=item["source_quote"],
        )

    def assert_generation_not_called(self, generate_mock):
        generate_mock.assert_not_called()

    def test_edit_get_does_not_change_card_or_database(self):
        original_question = self.card2.question
        original_answer = self.card2.answer
        original_quote = self.card2.source_quote

        initial_card_count = Flashcard.objects.count()

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Flashcard.objects.count(), initial_card_count)

        self.card2.refresh_from_db()

        self.assertEqual(self.card2.question, original_question)
        self.assertEqual(self.card2.answer, original_answer)
        self.assertEqual(self.card2.source_quote, original_quote)

        self.assert_generation_not_called(mock_generate)

    def test_valid_post_updates_only_selected_card_and_resets_verification(self):
        self.card2.is_verified = True
        self.card2.save(update_fields=["is_verified"])

        original_card1 = self.card1.question
        original_card3 = self.card3.question

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(
                self.edit_url,
                self.valid_edit_data,
            )

        self.assertRedirects(response, self.detail_url)

        self.card2.refresh_from_db()
        self.card1.refresh_from_db()
        self.card3.refresh_from_db()

        self.assertEqual(
            self.card2.question,
            self.valid_edit_data["question"],
        )
        self.assertEqual(
            self.card2.answer,
            self.valid_edit_data["answer"],
        )
        self.assertEqual(
            self.card2.source_quote,
            self.valid_edit_data["source_quote"],
        )

        self.assertFalse(self.card2.is_verified)

        self.assertEqual(self.card1.question, original_card1)
        self.assertEqual(self.card3.question, original_card3)

        self.assertEqual(Flashcard.objects.count(), 3)
        self.assertEqual(Source.objects.count(), 1)

        self.assert_generation_not_called(mock_generate)

    def test_empty_question_is_rejected_without_database_writes(self):
        original_question = self.card2.question

        invalid_data = {
            **self.valid_edit_data,
            "question": "",
        }

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.edit_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        self.card2.refresh_from_db()

        self.assertEqual(self.card2.question, original_question)
        self.assertEqual(Flashcard.objects.count(), 3)

        self.assert_generation_not_called(mock_generate)

    def test_question_longer_than_model_limit_is_rejected(self):
        original_question = self.card2.question

        invalid_data = {
            **self.valid_edit_data,
            "question": "Q" * 301,
        }

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.edit_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        self.card2.refresh_from_db()

        self.assertEqual(self.card2.question, original_question)
        self.assertEqual(Flashcard.objects.count(), 3)

        self.assert_generation_not_called(mock_generate)

    def test_quote_not_present_in_source_is_rejected(self):
        original_quote = self.card2.source_quote

        invalid_data = {
            **self.valid_edit_data,
            "source_quote": "This sentence does not exist in the source.",
        }

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.edit_url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "source_quote",
            response.context["form"].errors,
        )

        self.card2.refresh_from_db()

        self.assertEqual(self.card2.source_quote, original_quote)
        self.assertEqual(Flashcard.objects.count(), 3)

        self.assert_generation_not_called(mock_generate)

    def test_forged_source_position_and_verification_fields_are_ignored(self):
        other_source = Source.objects.create(
            title="Another source",
            text=DEMO_TEXT,
            generation_mode="DEMO",
        )

        original_position = self.card2.position
        original_source_id = self.card2.source_id

        forged_data = {
            **self.valid_edit_data,
            "source": str(other_source.pk),
            "position": "99",
            "is_verified": "true",
        }

        self.card2.is_verified = True
        self.card2.save(update_fields=["is_verified"])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.edit_url, forged_data)

        self.assertRedirects(response, self.detail_url)

        self.card2.refresh_from_db()

        self.assertEqual(self.card2.source_id, original_source_id)
        self.assertEqual(self.card2.position, original_position)

        # A successful edit resets verification regardless of forged POST data.
        self.assertFalse(self.card2.is_verified)

        self.assertEqual(Flashcard.objects.count(), 3)
        self.assertEqual(Source.objects.count(), 2)

        self.assert_generation_not_called(mock_generate)

    def test_delete_get_displays_confirmation_without_deleting(self):
        initial_card_count = Flashcard.objects.count()

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Flashcard.objects.count(), initial_card_count)
        self.assertTrue(
            Flashcard.objects.filter(pk=self.card2.pk).exists()
        )

        self.assert_generation_not_called(mock_generate)

    def test_cancel_delete_keeps_card_and_source(self):
        initial_card_count = Flashcard.objects.count()

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(self.delete_url)

        self.assertEqual(response.status_code, 200)

        # Opening the confirmation page is not a deletion.
        self.assertTrue(
            Flashcard.objects.filter(pk=self.card2.pk).exists()
        )
        self.assertEqual(Flashcard.objects.count(), initial_card_count)
        self.assertTrue(
            Source.objects.filter(pk=self.source.pk).exists()
        )

        self.assert_generation_not_called(mock_generate)

    def test_delete_post_deletes_only_selected_card(self):
        selected_card_id = self.card2.pk
        first_card_id = self.card1.pk
        third_card_id = self.card3.pk
        source_id = self.source.pk

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(self.delete_url)

        self.assertRedirects(response, self.detail_url)

        self.assertFalse(
            Flashcard.objects.filter(pk=selected_card_id).exists()
        )
        self.assertTrue(
            Flashcard.objects.filter(pk=first_card_id).exists()
        )
        self.assertTrue(
            Flashcard.objects.filter(pk=third_card_id).exists()
        )
        self.assertTrue(
            Source.objects.filter(pk=source_id).exists()
        )

        self.assertEqual(Flashcard.objects.count(), 2)
        self.assertEqual(Source.objects.count(), 1)

        self.assert_generation_not_called(mock_generate)

    def test_review_get_is_not_allowed(self):
        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(self.review_url)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.card2.is_verified)

        self.assert_generation_not_called(mock_generate)

    def test_verify_post_changes_review_status(self):
        self.assertFalse(self.card2.is_verified)

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(
                self.review_url,
                {"action": "verify"},
            )

        self.assertRedirects(response, self.detail_url)

        self.card2.refresh_from_db()
        self.assertTrue(self.card2.is_verified)

        self.assert_generation_not_called(mock_generate)

    def test_repeated_verify_post_keeps_card_verified(self):
        with patch("study.views.generate_cards") as mock_generate:
            first_response = self.client.post(
                self.review_url,
                {"action": "verify"},
            )
            second_response = self.client.post(
                self.review_url,
                {"action": "verify"},
            )

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)

        self.card2.refresh_from_db()
        self.assertTrue(self.card2.is_verified)

        self.assertEqual(Flashcard.objects.count(), 3)

        self.assert_generation_not_called(mock_generate)

    def test_reset_post_changes_verified_card_to_pending(self):
        self.card2.is_verified = True
        self.card2.save(update_fields=["is_verified"])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(
                self.review_url,
                {"action": "reset"},
            )

        self.assertRedirects(response, self.detail_url)

        self.card2.refresh_from_db()
        self.assertFalse(self.card2.is_verified)

        self.assert_generation_not_called(mock_generate)

    def test_invalid_review_action_returns_400_without_changing_status(self):
        self.card2.is_verified = True
        self.card2.save(update_fields=["is_verified"])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(
                self.review_url,
                {"action": "invalid"},
            )

        self.assertEqual(response.status_code, 400)

        self.card2.refresh_from_db()
        self.assertTrue(self.card2.is_verified)

        self.assert_generation_not_called(mock_generate)

    def test_filters_show_only_cards_from_current_source(self):
        other_source = Source.objects.create(
            title="Other source",
            text=DEMO_TEXT,
            generation_mode="DEMO",
        )

        other_card = Flashcard.objects.create(
            source=other_source,
            position=1,
            question="Question from another source",
            answer="Answer from another source",
            source_quote=DEMO_CARDS[0]["source_quote"],
        )

        self.card1.is_verified = True
        self.card1.save(update_fields=["is_verified"])

        self.card2.is_verified = False
        self.card2.save(update_fields=["is_verified"])

        self.card3.is_verified = True
        self.card3.save(update_fields=["is_verified"])

        with patch("study.views.generate_cards") as mock_generate:
            all_response = self.client.get(self.detail_url)
            pending_response = self.client.get(
                self.detail_url,
                {"status": "pending"},
            )
            verified_response = self.client.get(
                self.detail_url,
                {"status": "verified"},
            )

        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(pending_response.status_code, 200)
        self.assertEqual(verified_response.status_code, 200)

        self.assertEqual(
            list(all_response.context["cards"]),
            [self.card1, self.card2, self.card3],
        )
        self.assertEqual(
            list(pending_response.context["cards"]),
            [self.card2],
        )
        self.assertEqual(
            list(verified_response.context["cards"]),
            [self.card1, self.card3],
        )

        for response in (
            all_response,
            pending_response,
            verified_response,
        ):
            self.assertEqual(response.context["total_count"], 3)
            self.assertEqual(response.context["verified_count"], 2)
            self.assertEqual(response.context["pending_count"], 1)

            self.assertNotContains(
                response,
                "Question from another source",
            )

        self.assertTrue(
            Flashcard.objects.filter(pk=other_card.pk).exists()
        )

        self.assert_generation_not_called(mock_generate)

    def test_unknown_filter_value_displays_all_current_source_cards(self):
        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(
                self.detail_url,
                {"status": "unknown"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["cards"]),
            [self.card1, self.card2, self.card3],
        )
        self.assertEqual(response.context["status"], "all")

        self.assert_generation_not_called(mock_generate)

    def test_empty_filter_result_keeps_global_counts(self):
        self.card1.is_verified = True
        self.card1.save(update_fields=["is_verified"])

        self.card2.is_verified = True
        self.card2.save(update_fields=["is_verified"])

        self.card3.is_verified = True
        self.card3.save(update_fields=["is_verified"])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(
                self.detail_url,
                {"status": "pending"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cards"]), [])

        self.assertEqual(response.context["total_count"], 3)
        self.assertEqual(response.context["verified_count"], 3)
        self.assertEqual(response.context["pending_count"], 0)

        self.assert_generation_not_called(mock_generate)

    def test_empty_collection_displays_zero_counts(self):
        self.source.cards.all().delete()

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cards"]), [])

        self.assertEqual(response.context["total_count"], 0)
        self.assertEqual(response.context["verified_count"], 0)
        self.assertEqual(response.context["pending_count"], 0)

        self.assert_generation_not_called(mock_generate)

    def test_nonexistent_card_edit_returns_404(self):
        url = reverse("card_edit", args=[999999])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

        self.assert_generation_not_called(mock_generate)

    def test_nonexistent_card_delete_returns_404(self):
        url = reverse("card_delete", args=[999999])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

        self.assert_generation_not_called(mock_generate)

    def test_nonexistent_card_review_returns_404(self):
        url = reverse("card_review", args=[999999])

        with patch("study.views.generate_cards") as mock_generate:
            response = self.client.post(
                url,
                {"action": "verify"},
            )

        self.assertEqual(response.status_code, 404)

        self.assert_generation_not_called(mock_generate)

    def test_edit_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        with patch("study.views.generate_cards") as mock_generate:
            response = csrf_client.post(
                self.edit_url,
                self.valid_edit_data,
            )

        self.assertEqual(response.status_code, 403)

        self.card2.refresh_from_db()
        self.assertEqual(
            self.card2.question,
            DEMO_CARDS[1]["question"],
        )

        self.assert_generation_not_called(mock_generate)

    def test_delete_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        with patch("study.views.generate_cards") as mock_generate:
            response = csrf_client.post(self.delete_url)

        self.assertEqual(response.status_code, 403)

        self.assertTrue(
            Flashcard.objects.filter(pk=self.card2.pk).exists()
        )
        self.assertEqual(Flashcard.objects.count(), 3)

        self.assert_generation_not_called(mock_generate)

    def test_review_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        with patch("study.views.generate_cards") as mock_generate:
            response = csrf_client.post(
                self.review_url,
                {"action": "verify"},
            )

        self.assertEqual(response.status_code, 403)

        self.card2.refresh_from_db()
        self.assertFalse(self.card2.is_verified)

        self.assert_generation_not_called(mock_generate)