import pytest

from apps.accounts.models import User
from apps.cadastro.models import Cliente, Concessionaria, UnidadeConsumidora, Usina
from apps.core.models import Integradora


@pytest.fixture(autouse=True)
def _sem_clima_real(settings):
    """Testes nunca acessam a internet; quem precisa do clima liga e simula a resposta."""
    from apps.integracoes import clima

    settings.CLIMA_PROVIDER = ""
    clima.limpar_cache()
    yield
    clima.limpar_cache()


@pytest.fixture
def cosern(db):
    return Concessionaria.objects.get_or_create(
        sigla="cosern", defaults={"nome": "Neoenergia Cosern", "uf": "RN", "layout_fatura": "cosern"}
    )[0]


@pytest.fixture
def integradora_a(db):
    return Integradora.objects.create(razao_social="Solar A Ltda", cnpj="11.222.333/0001-81")


@pytest.fixture
def integradora_b(db):
    return Integradora.objects.create(razao_social="Solar B Ltda", cnpj="11.444.777/0001-61")


def _user(username, integradora, papel=User.Papel.GESTOR):
    return User.objects.create_user(username=username, password="senha-forte-123", integradora=integradora,
                                    papel=papel)


@pytest.fixture
def gestor_a(integradora_a):
    return _user("gestor_a", integradora_a)


@pytest.fixture
def tecnico_a(integradora_a):
    return _user("tecnico_a", integradora_a, User.Papel.TECNICO)


@pytest.fixture
def gestor_b(integradora_b):
    return _user("gestor_b", integradora_b)


@pytest.fixture
def cliente_a(integradora_a):
    return Cliente.objects.create(integradora=integradora_a, nome="Padaria A", documento="529.982.247-25")


@pytest.fixture
def cliente_b(integradora_b):
    return Cliente.objects.create(integradora=integradora_b, nome="Mercado B", documento="111.444.777-35")


@pytest.fixture
def uc_a(cliente_a, cosern):
    return UnidadeConsumidora.objects.create(
        integradora=cliente_a.integradora, cliente=cliente_a, concessionaria=cosern, numero_uc="7010453067",
        tipo_ligacao="tri", municipio="Natal", uf="RN",
    )


@pytest.fixture
def uc_b(cliente_b, cosern):
    return UnidadeConsumidora.objects.create(
        integradora=cliente_b.integradora, cliente=cliente_b, concessionaria=cosern, numero_uc="7000000001"
    )


@pytest.fixture
def usina_b(uc_b):
    return Usina.objects.create(integradora=uc_b.integradora, nome="Usina B", uc_geradora=uc_b)
