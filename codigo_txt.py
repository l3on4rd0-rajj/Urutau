#!/usr/bin/env python3
"""Exporta arquivos para um pacote TXT e restaura seus bytes e permissões."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def exportar(origem, destino, tamanho_parte=1024):
    if tamanho_parte < 4 or tamanho_parte % 4:
        raise ValueError('O tamanho da parte deve ser múltiplo de 4 e pelo menos 4 bytes.')
    if origem.is_symlink():
        raise ValueError('Links simbólicos não são suportados.')
    origem = origem.resolve()
    destino = destino.absolute()
    if not origem.exists() or origem.is_symlink():
        raise ValueError('A origem deve ser um arquivo ou pasta existente, sem link simbólico.')
    if destino.exists():
        raise ValueError('O destino já existe. Escolha uma nova pasta.')
    if origem.is_dir() and destino.resolve().is_relative_to(origem):
        raise ValueError('O pacote deve ficar fora da pasta de origem.')
    entradas = []
    contador = 0
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = Path(tempfile.mkdtemp(prefix='.codigo-txt-', dir=destino.parent))
    try:
        caminhos = sorted(origem.rglob('*')) if origem.is_dir() else [origem]
        for caminho in caminhos:
            if caminho.is_symlink():
                raise ValueError(f'Link simbólico não suportado: {caminho}')
            nome = caminho.relative_to(origem).as_posix() if origem.is_dir() else caminho.name
            item = {'caminho': nome, 'modo': caminho.stat().st_mode & 0o777}
            if caminho.is_dir():
                item['tipo'] = 'pasta'
            elif caminho.is_file():
                dados = caminho.read_bytes()
                codificado = base64.b64encode(dados)
                partes = []
                for inicio in range(0, max(1, len(codificado)), tamanho_parte):
                    if contador > 99999999:
                        raise ValueError('Limite de partes excedido.')
                    txt = f'{contador:08d}.txt'
                    contador += 1
                    (temporario / txt).write_bytes(codificado[inicio:inicio + tamanho_parte])
                    partes.append(txt)
                item.update(tipo='arquivo', partes=partes, sha256=hashlib.sha256(dados).hexdigest())
            else:
                raise ValueError(f'Tipo de arquivo não suportado: {caminho}')
            entradas.append(item)
        manifesto = {'versao': 2, 'codificacao': 'base64', 'entradas': entradas}
        (temporario / 'manifesto.txt').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
        temporario.rename(destino)
    except BaseException:
        shutil.rmtree(temporario)
        raise
    print(f'Exportado para {destino}')


def restaurar(pacote, destino):
    destino = destino.absolute()
    if destino.exists():
        raise ValueError('O destino já existe. A restauração exige uma nova pasta.')
    manifesto = json.loads((pacote / 'manifesto.txt').read_text(encoding='utf-8'))
    if manifesto.get('versao') not in (1, 2) or manifesto.get('codificacao') != 'base64':
        raise ValueError('Formato de pacote não suportado.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = Path(tempfile.mkdtemp(prefix='.codigo-restaurado-', dir=destino.parent))
    vistos = set()
    pastas = []
    try:
        for item in manifesto['entradas']:
            nome = item['caminho']
            relativo = PurePosixPath(nome)
            if not nome or relativo.is_absolute() or '..' in relativo.parts or '\\' in nome:
                raise ValueError(f'Caminho inválido: {nome}')
            if relativo == PurePosixPath('.') or relativo in vistos:
                raise ValueError(f'Caminho duplicado ou inválido: {nome}')
            vistos.add(relativo)
            alvo = temporario.joinpath(*relativo.parts)
            modo = item['modo']
            if not isinstance(modo, int) or not 0 <= modo <= 0o777:
                raise ValueError(f'Permissões inválidas: {nome}')
            if item['tipo'] == 'pasta':
                alvo.mkdir(parents=True, exist_ok=True)
                pastas.append((alvo, modo))
            elif item['tipo'] == 'arquivo':
                partes = [item['txt']] if manifesto['versao'] == 1 else item['partes']
                if not isinstance(partes, list) or not partes:
                    raise ValueError('Lista de partes inválida.')
                blocos = []
                for txt in partes:
                    if not isinstance(txt, str) or len(txt) != 12 or not txt[:8].isdigit() or txt[8:] != '.txt':
                        raise ValueError('Nome de arquivo TXT inválido.')
                    fonte = pacote / txt
                    if fonte.is_symlink():
                        raise ValueError('Links simbólicos não são permitidos no pacote.')
                    blocos.append(base64.b64decode(fonte.read_bytes(), validate=True))
                dados = b''.join(blocos)
                if hashlib.sha256(dados).hexdigest() != item['sha256']:
                    raise ValueError(f'Conteúdo corrompido: {nome}')
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with alvo.open('xb') as arquivo:
                    arquivo.write(dados)
                alvo.chmod(modo)
            else:
                raise ValueError('Tipo de entrada inválido.')
        for pasta, modo in sorted(pastas, key=lambda par: len(par[0].parts), reverse=True):
            pasta.chmod(modo)
        temporario.rename(destino)
    except BaseException:
        for raiz, diretorios, _ in os.walk(temporario):
            os.chmod(raiz, 0o700)
            for diretorio in diretorios:
                os.chmod(Path(raiz) / diretorio, 0o700)
        shutil.rmtree(temporario)
        raise
    print(f'Restaurado em {destino}')


def gerar_docker(pacote, destino):
    """Gera contexto Docker para projeto Node.js com server.js, sem dependências."""
    destino = destino.absolute()
    if destino.exists():
        raise ValueError('O destino já existe. Escolha uma nova pasta.')
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = Path(tempfile.mkdtemp(prefix='.codigo-docker-', dir=destino.parent))
    try:
        # Valida a restauração sem executar o conteúdo do pacote.
        restaurar(pacote, temporario / 'validacao')
        if not (temporario / 'validacao' / 'server.js').is_file():
            raise ValueError('Este modelo Docker exige server.js na raiz do projeto Node.js.')
        shutil.rmtree(temporario / 'validacao')
        (temporario / 'pacote').mkdir()
        manifesto = json.loads((pacote / 'manifesto.txt').read_text(encoding='utf-8'))
        nomes = {'manifesto.txt'}
        for item in manifesto['entradas']:
            if item['tipo'] == 'arquivo':
                nomes.update([item['txt']] if manifesto['versao'] == 1 else item['partes'])
        for nome in nomes:
            shutil.copyfile(pacote / nome, temporario / 'pacote' / nome)
        shutil.copyfile(Path(__file__), temporario / 'codigo_txt.py')
        (temporario / 'Dockerfile').write_text('''FROM python:3.13-slim AS restauracao
WORKDIR /build
COPY codigo_txt.py ./codigo_txt.py
COPY pacote/ ./pacote/
RUN python codigo_txt.py restaurar pacote /restaurado && chmod 755 /restaurado

FROM node:24-bookworm-slim
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=restauracao --chown=node:node /restaurado/ /app/
USER node
EXPOSE 3000
CMD ["node", "server.js"]
''', encoding='utf-8')
        (temporario / '.dockerignore').write_text('*\n!Dockerfile\n!codigo_txt.py\n!pacote/\n!pacote/**\n', encoding='utf-8')
        temporario.rename(destino)
    except BaseException:
        shutil.rmtree(temporario)
        raise
    print(f'Contexto Docker gerado em {destino}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comando', choices=['exportar', 'restaurar', 'docker'])
    parser.add_argument('origem', type=Path)
    parser.add_argument('destino', type=Path)
    parser.add_argument('--tamanho-parte', type=int, default=1024,
                        help='Limite de bytes por TXT na exportação (padrão: 1024; múltiplo de 4).')
    args = parser.parse_args()
    try:
        if args.comando == 'exportar':
            exportar(args.origem, args.destino, args.tamanho_parte)
        elif args.comando == 'restaurar':
            restaurar(args.origem, args.destino)
        else:
            gerar_docker(args.origem, args.destino)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        parser.exit(1, f'Erro: {erro}\n')


if __name__ == '__main__':
    main()
