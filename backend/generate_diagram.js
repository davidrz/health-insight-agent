// Script para generar imagen del diagrama de arquitectura
// Requiere: npm install -g @mermaid-js/mermaid-cli

const fs = require('fs');

// Extraer el diagrama Mermaid del archivo markdown
const markdownContent = fs.readFileSync('architecture_diagram.md', 'utf8');

// Buscar el primer bloque de código mermaid
const mermaidMatch = markdownContent.match(/```mermaid\n([\s\S]*?)\n```/);

if (mermaidMatch) {
    const mermaidCode = mermaidMatch[1];

    // Guardar el código Mermaid en un archivo separado
    fs.writeFileSync('architecture_diagram.mmd', mermaidCode);

    console.log('✅ Diagrama extraído a architecture_diagram.mmd');
    console.log('');
    console.log('Para generar la imagen, ejecuta:');
    console.log('npm install -g @mermaid-js/mermaid-cli');
    console.log('mmdc -i architecture_diagram.mmd -o architecture_diagram.png');
    console.log('mmdc -i architecture_diagram.mmd -o architecture_diagram.svg');
} else {
    console.log('❌ No se encontró diagrama Mermaid en el archivo');
}