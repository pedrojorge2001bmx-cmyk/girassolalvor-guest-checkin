# Alvor Guest Check-in

Aplicação Flask para um único alojamento local: formulário de hóspedes por reserva, painel privado e exportação CSV de trabalho.

## Instalação local (demonstração)

1. Instale Python 3.11+.
2. Execute `python -m venv .venv` e ative o ambiente virtual.
3. Execute `pip install -r requirements.txt`.
4. Copie `.env.example` para `.env`; defina `SECRET_KEY` com um valor aleatório de pelo menos 32 bytes (por exemplo `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
5. Para testes **apenas locais por HTTP**, use `COOKIE_SECURE=0` no `.env`. Em produção mantenha `COOKIE_SECURE=1` e HTTPS.
6. Execute `python app.py` e abra `http://127.0.0.1:5000/setup` para criar o primeiro utilizador.
7. Abra `/login`, crie uma reserva e copie o link de check-in gerado.

## Antes de utilizar com hóspedes reais

**Este é um MVP para instalação e validação, não uma implementação de produção auditada.** Não introduza dados reais de documentos antes de implementar e validar: HTTPS, backups cifrados, proteção da base de dados, limitação de tentativas de login, gestão segura de segredos, registo de acessos, monitorização, políticas de conservação e eliminação automática, política de privacidade completa, análise RGPD, controlo de acesso, procedimentos para pedidos dos titulares, testes de segurança e configuração de alojamento. Use um serviço de alojamento com suporte adequado a dados pessoais e contrato de subcontratação de tratamento.

O endpoint `/setup` só funciona antes de existir a primeira conta. Proteja a implantação contra acesso público até configurar o administrador.

Não inclui envio automático ao SIBA, ficheiro oficial validado, nem upload de fotografias de passaportes. O CSV é apenas uma exportação de apoio. Verifique campos, prazos e especificação de integração diretamente com as fontes oficiais e com o responsável pelo cumprimento legal.

## Produção (após endurecimento)

Um servidor WSGI como `gunicorn app:app` atrás de proxy HTTPS. Configure um domínio e base de dados/armazenamento com encriptação e backups. SQLite é adequado a demonstração e pequenos testes, mas avalie PostgreSQL gerido para operação real.
