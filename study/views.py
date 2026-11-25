from django.conf import settings
from django.db import DatabaseError, transaction
from django.shortcuts import render, redirect, get_object_or_404

from .forms import SourceForm
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

    return render(
        request,
        "study/home.html",
        {
            "form": form,
            "sources": sources,
            "generation_mode": getattr(
                settings,
                "TEACHME_MODE",
                "DEMO",
            ).upper(),
        },
    )


def source_detail(request, pk):
    source = get_object_or_404(
        Source,
        pk=pk,
    )

    cards = source.cards.order_by("position", "id")

    return render(
        request,
        "study/source_detail.html",
        {
            "source": source,
            "cards": cards,
        },
    )