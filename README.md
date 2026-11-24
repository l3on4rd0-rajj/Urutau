# Urutau

O Urutau inclui um validador Python de integridade de pacotes TXT e exemplos de servidores HTTP em Node.js.

## Validar o pacote de exemplo

Com Python 3.9 ou mais recente, execute na raiz do repositório:

```bash
python3 validar_pacote.py exemplos/pacote-integridade
```

O resultado esperado é `Integridade confirmada para 1 arquivo(s).`. O pacote contém uma mensagem de texto. O validador lê o manifesto, verifica o SHA-256 de cada entrada e retorna código 1 se encontrar erro. A conferência compara o conteúdo com o manifesto fornecido e não autentica a origem do pacote.

## Executar o exemplo web

Com Node.js 18 ou mais recente:

```bash
cd first-poc/exemplo-node
npm start
```

Abra `http://127.0.0.1:3000` para ver a página. Use Ctrl+C para encerrar o servidor. O exemplo usa apenas módulos nativos do Node.js.
