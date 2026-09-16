# PPI-PROPEG

Plataforma para cadastro, tramitação e acompanhamento de projetos institucionais da PROPEG/UFAC.

## Implantação no Render

O repositório inclui um Blueprint em `render.yaml` com serviço Django e PostgreSQL. No primeiro deploy, informe no painel do Render os segredos marcados como obrigatórios: `CLOUDINARY_URL`, `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL`, `ADMIN_CPF`, `ADMIN_EMAIL` e `ADMIN_PASSWORD`.

O plano gratuito é adequado somente para validação: o serviço pode suspender por inatividade e o PostgreSQL gratuito expira após 30 dias. Para operação contínua, altere os planos do serviço web e do banco antes do uso institucional.
