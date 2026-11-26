
from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404

from .forms import SourceForm, FlashcardForm
from .models import Source, Flashcard
from .services import generate_cards, GenerationError


def home(request):
    if request.method == "POST":
        form = SourceForm(request.POST)

        if form.is_valid():
            title = form.cleaned_data["title"]
            text = form.cleaned_data["text"]

            # Generate and validate all cards before database transaction.
            try:
                cards = generate_cards(text)

            except GenerationError as exc:
                form.add_error(None, str(exc))

            except Exception:
                form.add_error(
                    None,
                    "An unexpected error occurred during card generation. "
                    "Please try again.",
                )

            else:
                generation_mode = getattr(
                    settings,
                    "TEACHME_MODE",
                    "DEMO",
                )

                if not isinstance(generation_mode, str):
                    generation_mode = "DEMO"

                generation_mode = generation_mode.strip().upper()

                try:
                    with transaction.atomic():
                        source = Source.objects.create(
                            title=title,
                            text=text,
                            generation_mode=generation_mode,
                        )

                        Flashcard.objects.bulk_create([
                            Flashcard(
                                source=source,
                                position=position,
                                question=card["question"],
                                answer=card["answer"],
                                source_quote=card["source_quote"],
                            )
                            for position, card in enumerate(cards, start=1)
                        ])

                except DatabaseError:
                    form.add_error(
                        None,
                        "The study material could not be saved. "
                        "Please try again.",
                    )

                else:
                    return redirect(
                        "source_detail",
                        pk=source.pk,
                    )

    else:
        form = SourceForm()

    sources = Source.objects.order_by("-created_at")

    generation_mode = getattr(
        settings,
        "TEACHME_MODE",
        "DEMO",
    )

    if not isinstance(generation_mode, str):
        generation_mode = "DEMO"

    return render(
        request,
        "study/home.html",
        {
            "form": form,
            "sources": sources,
            "generation_mode": generation_mode.upper(),
        },
    )


def source_detail(request, pk):
    source = get_object_or_404(
        Source,
        pk=pk,
    )

    # Get all cards belonging to this source.
    all_cards = source.cards.all()

    # Calculate counts before applying the selected filter.
    total_count = all_cards.count()
    verified_count = all_cards.filter(is_verified=True).count()
    pending_count = total_count - verified_count

    # Read and validate the requested filter.
    status = request.GET.get("status", "all")

    if status not in ("all", "pending", "verified"):
        status = "all"

    # Filter cards in the database, not in the template.
    if status == "pending":
        cards = all_cards.filter(
            is_verified=False,
        ).order_by("position", "pk")

    elif status == "verified":
        cards = all_cards.filter(
            is_verified=True,
        ).order_by("position", "pk")

    else:
        cards = all_cards.order_by(
            "position",
            "pk",
        )

    return render(
        request,
        "study/source_detail.html",
        {
            "source": source,
            "cards": cards,
            "total_count": total_count,
            "verified_count": verified_count,
            "pending_count": pending_count,
            "status": status,
        },
    )


def card_edit(request, pk):
    card = get_object_or_404(
        Flashcard,
        pk=pk,
    )

    if request.method == "POST":
        form = FlashcardForm(
            request.POST,
            instance=card,
        )

        if form.is_valid():
            edited_card = form.save(commit=False)

            # Any successful edit resets the verification status.
            edited_card.is_verified = False
            edited_card.save()

            return redirect(
                "source_detail",
                pk=card.source.pk,
            )

    elif request.method == "GET":
        form = FlashcardForm(
            instance=card,
        )

    else:
        return HttpResponseNotAllowed(["GET", "POST"])

    return render(
        request,
        "study/card_form.html",
        {
            "form": form,
            "card": card,
            "source": card.source,
        },
    )


def card_delete(request, pk):
    card = get_object_or_404(
        Flashcard,
        pk=pk,
    )

    source_id = card.source_id

    if request.method == "POST":
        card.delete()

        return redirect(
            "source_detail",
            pk=source_id,
        )

    if request.method == "GET":
        return render(
            request,
            "study/card_confirm_delete.html",
            {
                "card": card,
                "source": card.source,
            },
        )

    return HttpResponseNotAllowed(["GET", "POST"])


def card_review(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    card = get_object_or_404(
        Flashcard,
        pk=pk,
    )

    action = request.POST.get("action")

    if action == "verify":
        card.is_verified = True

    elif action == "reset":
        card.is_verified = False

    else:
        return HttpResponse("Invalid action.", status=400)

    card.save(update_fields=["is_verified"])

    return redirect(
        "source_detail",
        pk=card.source_id,
    )
