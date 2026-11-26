from django import forms

from .models import Flashcard


class SourceForm(forms.Form):
    title = forms.CharField(
        max_length=120,
        required=True,
        strip=True,
        label='Тақырып',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Мысалы: Компьютерные сети',
        }),
    )

    text = forms.CharField(
        min_length=80,
        max_length=12000,
        required=True,
        strip=True,
        label='Оқу мәтіні',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'Оқу мәтінін осында енгізіңіз...',
        }),
    )

    def clean_text(self):
        text = self.cleaned_data['text']
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        return text


class FlashcardForm(forms.ModelForm):
    class Meta:
        model = Flashcard
        fields = ['question', 'answer', 'source_quote']
        widgets = {
            'question': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'answer': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
            }),
            'source_quote': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
            }),
        }
        labels = {
            'question': 'Сұрақ',
            'answer': 'Жауап',
            'source_quote': 'Бастапқы мәтіннен дәйексөз',
        }

    def clean_source_quote(self):
        source_quote = self.cleaned_data['source_quote']
        source_quote = source_quote.replace('\r\n', '\n').replace('\r', '\n')

        source_text = self.instance.source.text
        source_text = source_text.replace('\r\n', '\n').replace('\r', '\n')

        if source_quote not in source_text:
            raise forms.ValidationError(
                'Дәйексөз бастапқы мәтіннің ішінде дәл кездесуі керек. '
                'Бастапқы мәтінмен салыстырып, дәйексөзді түзетіңіз.'
            )

        return source_quote