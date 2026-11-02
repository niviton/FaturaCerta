from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.cadastro.models import Cliente
from apps.core.forms import SecoesMixin

from .models import User


class UsuarioForm(SecoesMixin, forms.ModelForm):
    """Cadastro de usuário.

    Administrador geral: escolhe qualquer papel e integradora.
    Gestor da integradora: só cria gestor, técnico e cliente da própria integradora.
    """

    senha = forms.CharField(label="Senha", required=False, widget=forms.PasswordInput(render_value=False),
                            help_text="Mínimo de 8 caracteres. Na edição, deixe vazio para manter a atual.")

    secoes = [
        ("Pessoa", "", ["first_name", "last_name", "email", "telefone"]),
        ("Acesso", "O papel define o que a pessoa vê.", ["username", "senha", "papel", "integradora", "cliente",
                                                          "is_active"]),
    ]

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "telefone", "username", "papel", "integradora", "cliente",
                  "is_active"]
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "username": "Usuário (login)",
                  "is_active": "Acesso ativo"}

    def __init__(self, *args, integradora=None, admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.integradora_fixa = None if admin else integradora
        self.fields["cliente"].label_from_instance = lambda c: f"{c} ({c.integradora})"
        if not admin:
            self.fields["papel"].choices = [c for c in User.Papel.choices if c[0] != User.Papel.ADMIN_INTERNO]
            del self.fields["integradora"]
            self.fields["cliente"].queryset = Cliente.objects.filter(integradora=integradora)
        else:
            self.fields["cliente"].queryset = Cliente.objects.select_related("integradora")
        self.fields["cliente"].help_text = "Só para o papel cliente final."
        if self.instance.pk is None:
            self.fields["senha"].required = True

    def clean_senha(self):
        s = self.cleaned_data.get("senha")
        if s:
            validate_password(s, self.instance)
        return s

    def clean(self):
        data = super().clean()
        if self.integradora_fixa is not None:
            self.instance.integradora = self.integradora_fixa
        papel = data.get("papel")
        if papel != User.Papel.CLIENTE:
            data["cliente"] = None
            self.instance.cliente = None
        if papel == User.Papel.ADMIN_INTERNO:
            data["integradora"] = None
        if papel == User.Papel.CLIENTE and data.get("cliente") and self.integradora_fixa is None:
            self.instance.integradora = data["cliente"].integradora
            data["integradora"] = data["cliente"].integradora
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("senha"):
            user.set_password(self.cleaned_data["senha"])
        if user.papel == User.Papel.ADMIN_INTERNO:
            user.is_staff = True
        if commit:
            user.save()
        return user


class AcessoPortalForm(forms.Form):
    username = forms.CharField(label="Usuário (login)", max_length=150)
    email = forms.EmailField(label="E-mail", required=False)
    senha = forms.CharField(label="Senha inicial", widget=forms.PasswordInput, min_length=8)

    def clean_username(self):
        u = self.cleaned_data["username"]
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Este usuário já existe.")
        return u
