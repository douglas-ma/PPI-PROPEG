from django.test import TestCase
from django.urls import reverse

from .forms import RegistroUsuarioForm


class RegistroUsuarioTests(TestCase):
    def test_cpf_formatado_e_normalizado_no_cadastro(self):
        form = RegistroUsuarioForm(data={
            'cpf': '529.982.247-25',
            'first_name': 'Usuário',
            'last_name': 'Teste',
            'email': 'usuario.teste@example.com',
            'perfil': 'aluno',
            'password': 'Senha@2026',
            'password2': 'Senha@2026',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['cpf'], '52998224725')

    def test_tela_registro_aplica_mascara_ao_campo_correto(self):
        resposta = self.client.get(reverse('home'))

        self.assertContains(resposta, "document.getElementById('id_cpf')")
        self.assertContains(resposta, "cpfReg.setAttribute('maxlength', '14')")
