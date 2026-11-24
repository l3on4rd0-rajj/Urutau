#!/usr/bin/env python3
"""Verifica a integridade de um pacote TXT sem gravar seu conteúdo."""

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path, PurePosixPath


def ler_arquivo(caminho):
    if caminho.is_symlink() or not caminho.is_file():
        raise ValueError(f'Arquivo regular esperado: {caminho.name!r}')
    return caminho.read_bytes()


def validar_pacote(pacote):
    manifesto = json.loads(ler_arquivo(pacote / 'manifesto.txt'))
    versao = manifesto['versao']
    if type(versao) is not int or versao not in (1, 2) or manifesto['codificacao'] != 'base64':
        raise ValueError('Formato de manifesto não suportado.')

    entradas = manifesto['entradas']
    if not isinstance(entradas, list):
        raise ValueError('A lista de entradas é inválida.')

    caminhos = set()
    arquivos = 0
    for entrada in entradas:
        nome = entrada['caminho']
        relativo = PurePosixPath(nome)
        if (relativo.is_absolute() or not relativo.parts or '..' in relativo.parts
                or '\\' in nome or '\x00' in nome or relativo in caminhos):
            raise ValueError(f'Caminho inválido ou duplicado: {nome!r}')
        caminhos.add(relativo)

        modo = entrada['modo']
        if type(modo) is not int or not 0 <= modo <= 0o777:
            raise ValueError(f'Permissões inválidas: {nome!r}')
        if entrada['tipo'] == 'pasta':
            continue
        if entrada['tipo'] != 'arquivo':
            raise ValueError(f'Tipo de entrada inválido: {nome!r}')

        partes = [entrada['txt']] if versao == 1 else entrada['partes']
        if not isinstance(partes, list) or not partes:
            raise ValueError(f'Lista de partes inválida: {nome!r}')
        esperado = entrada['sha256']
        if not isinstance(esperado, str) or not re.fullmatch(r'[0-9a-f]{64}', esperado):
            raise ValueError(f'SHA-256 inválido: {nome!r}')

        digest = hashlib.sha256()
        for parte in partes:
            if not isinstance(parte, str) or not re.fullmatch(r'[0-9]{8}\.txt', parte):
                raise ValueError(f'Nome de parte inválido: {nome!r}')
            digest.update(base64.b64decode(ler_arquivo(pacote / parte), validate=True))
        if digest.hexdigest() != esperado:
            raise ValueError(f'SHA-256 divergente: {nome!r}')
        arquivos += 1

    return arquivos


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='A verificação de integridade não comprova origem nem segurança do conteúdo.',
    )
    parser.add_argument('pacote', type=Path, help='Pasta que contém o manifesto.txt')
    args = parser.parse_args()
    try:
        arquivos = validar_pacote(args.pacote)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        parser.exit(1, f'Erro: {erro}\n')
    print(f'Integridade confirmada para {arquivos} arquivo(s).')


if __name__ == '__main__':
    main()
