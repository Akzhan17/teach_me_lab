
from django import forms


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
