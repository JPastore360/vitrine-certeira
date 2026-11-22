# Preparacao da integracao Mercado Livre — Vitrine Certeira

## Estado seguro
- Trabalho isolado na branch `ml-integracao-preparacao`.
- `main` e o site publicado nao foram alterados.
- O site atual e uma pagina estatica (GitHub Pages), com produtos cadastrados em array JavaScript no `index.html`.
- Nenhuma oferta do Mercado Livre deve ser publicada sem link de afiliado validado que atribua a comissao a conta do Julio.

## Objetivo
Adicionar uma fonte de produtos Mercado Livre ao Vitrine Certeira, com fotos reais, titulo, preco e link, mas com uma barreira de publicacao: produto so fica visivel se tiver link de afiliado validado.

## Arquitetura planejada
1. **Coletor/API**: buscar produtos usando endpoints oficiais do Mercado Livre, respeitando autenticacao, limites e termos.
2. **Normalizacao**: transformar resultados em um formato interno consistente (id, titulo, url_imagem, preco, moeda, url_produto, categoria, origem, url_afiliado, link_validado).
3. **Validacao afiliado**: manter os links de afiliado separados da URL comum do produto. Se nao existir link afiliado confirmado, o item permanece em rascunho e nao aparece no site.
4. **Catalogo**: gerar/atualizar um catalogo JSON para o frontend. Nao colocar Client Secret ou Access Token no HTML ou JavaScript publico.
5. **Frontend**: apresentar imagem real, preco, titulo, categoria e CTA com link afiliado. Atribuir `rel="nofollow sponsored noopener"` e abrir em nova aba.
6. **Analytics**: registrar cliques em eventos sem armazenar dados pessoais desnecessarios.

## Gate de publicacao (obrigatorio)
- URL afiliada existe.
- Link afiliado foi validado para o item certo e para a conta afiliada do usuario.
- Imagem e informacoes do produto foram obtidas de fonte permitida.
- Se qualquer validacao falhar, nao publicar o produto.

## Dependencias pendentes antes de ativar a coleta autenticada
- Criar/configurar aplicacao no DevCenter do Mercado Livre e obter Client ID/Client Secret.
- Definir Redirect URI e fluxo OAuth conforme documentacao oficial.
- Obter tokens por backend/ambiente seguro; tokens e segredos nunca ficam no frontend estatico.
- Confirmar no Programa de Afiliados qual fluxo oficial permite gerar/validar URLs afiliadas para cada produto. A API de produtos, por si, nao confirma atribuicao de comissao.
- Escolher hospedeiro de backend gratuito/adequado (GitHub Pages sozinho nao executa backend nem protege segredos).

## Implementacao por etapas
- [x] Confirmar acesso ao repositorio e leitura do arquivo principal.
- [x] Criar branch de trabalho separada.
- [x] Documentar arquitetura e regras de publicacao.
- [ ] Configurar aplicacao e OAuth Mercado Livre.
- [ ] Implementar backend seguro para busca/refresh token.
- [ ] Implementar conversao/validacao de URL afiliada.
- [ ] Criar catalogo JSON e validacoes automatizadas.
- [ ] Testar em preview antes de merge para main.

## Endpoints e documentacao
Consultar sempre a documentacao atual do Mercado Livre antes de codificar. Alguns endpoints de busca/consulta e autenticacao podem mudar, e chamadas com token podem retornar 401/403 se escopos ou autorizacao estiverem incorretos.

## Proximo passo
O usuario deve configurar a aplicacao no DevCenter Mercado Livre e concluir OAuth. A integracao so passa a buscar/publicar ofertas reais depois que credenciais e o mecanismo oficial de link afiliado forem confirmados.
