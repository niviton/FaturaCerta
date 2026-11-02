from django import forms


class SecoesMixin:
    """Agrupa os campos do form em seções com título e explicação.

    secoes = [("Título", "Para que servem estes dados", ["campo1", "campo2"]), ...]
    Campos fora de qualquer seção vão para uma seção final "Outros dados".
    """

    secoes: list[tuple[str, str, list[str]]] = []

    def secoes_renderizadas(self):
        usados, out = set(), []
        for titulo, ajuda, nomes in self.secoes:
            campos = [self[n] for n in nomes if n in self.fields]
            usados.update(nomes)
            if campos:
                out.append({"titulo": titulo, "ajuda": ajuda, "campos": campos})
        resto = [self[n] for n in self.fields if n not in usados]
        if resto:
            out.append({"titulo": "Outros dados" if out else "", "ajuda": "", "campos": resto})
        return out


DATA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
