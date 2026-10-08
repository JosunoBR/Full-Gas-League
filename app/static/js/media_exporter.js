/**
 * MediaExporter - Sistema FullGas League
 * Módulo unificado para exportação de cards e tabelas em PNG de alta resolução (4K / 3840px).
 */
(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.MediaExporter = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const MediaExporter = {
        /**
         * Exporta um elemento do DOM para PNG em alta resolução.
         * @param {HTMLElement|string} targetElementOrId Elemento ou ID do elemento
         * @param {string} filename Nome do arquivo de download
         * @param {Object} options Configurações adicionais
         */
        async exportElementToPng(targetElementOrId, filename, options = {}) {
            if (typeof html2canvas === 'undefined') {
                console.error('MediaExporter: html2canvas não está carregado na página.');
                alert('Biblioteca de renderização não carregada. Por favor, recarregue a página.');
                return;
            }

            const targetElement = typeof targetElementOrId === 'string'
                ? document.getElementById(targetElementOrId)
                : targetElementOrId;

            if (!targetElement) {
                console.error('MediaExporter: Elemento não encontrado:', targetElementOrId);
                return;
            }

            const targetWidth = options.targetWidth || 3840; // Padrão 4K
            const elementWidth = targetElement.offsetWidth || 1;
            const scale = options.scale || (targetWidth / elementWidth);

            const canvas = await html2canvas(targetElement, {
                backgroundColor: options.backgroundColor || '#0b0d11',
                scale: scale,
                useCORS: true,
                logging: false,
                ...(options.html2canvasOptions || {})
            });

            const link = document.createElement('a');
            link.href = canvas.toDataURL('image/png');
            link.download = filename || `export_${Date.now()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        },

        /**
         * Inicializa listeners de clique nos botões de exportação de classe .export-png-btn
         * @param {string} selector Seletor CSS dos botões
         */
        initButtons(selector = '.export-png-btn') {
            document.querySelectorAll(selector).forEach(btn => {
                if (btn._hasExportListener) return;
                btn._hasExportListener = true;

                btn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const targetId = btn.getAttribute('data-target-id');
                    const filename = btn.getAttribute('data-filename');

                    if (!targetId) {
                        console.warn('MediaExporter: Botão sem data-target-id definido.', btn);
                        return;
                    }

                    const originalHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

                    try {
                        await MediaExporter.exportElementToPng(targetId, filename);
                    } catch (err) {
                        console.error('MediaExporter: Erro na exportação para PNG:', err);
                        alert('Ocorreu um erro ao gerar a imagem PNG.');
                    } finally {
                        btn.disabled = false;
                        btn.innerHTML = originalHtml;
                    }
                });
            });
        }
    };

    // Auto-inicialização quando o DOM estiver pronto
    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => MediaExporter.initButtons());
        } else {
            MediaExporter.initButtons();
        }
    }

    return MediaExporter;
}));
