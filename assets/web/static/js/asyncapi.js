/**
 * AsyncAPI Documentation JavaScript for Irene Voice Assistant
 */

let asyncApiSpec = null;

function downloadFile(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function showSection(sectionId, clickedElement) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(s => s.classList.remove('active'));
    const loadingElement = document.querySelector('.loading');
    if (loadingElement) loadingElement.style.display = 'none';
    
    // Show selected section
    document.getElementById(sectionId).classList.add('active');
    
    // If called from click event, highlight the clicked nav item
    if (clickedElement) {
        clickedElement.classList.add('active');
    } else {
        // If called programmatically, find and highlight the matching nav item
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            if (item.onclick && item.onclick.toString().includes(sectionId)) {
                item.classList.add('active');
            }
        });
    }
}

function renderChannels() {
    const container = document.getElementById('channels-content');
    const channels = asyncApiSpec.channels || {};
    
    let html = '';
    for (const [path, channel] of Object.entries(channels)) {
        html += `
            <div class="operation">
                <div class="operation-header">📡 ${path}</div>
                <p><strong>Description:</strong> ${channel.description || 'WebSocket channel'}</p>
                ${channel.publish ? `
                    <div style="margin: 10px 0;">
                        <span class="operation-method method-publish">PUBLISH</span>
                        <strong>${channel.publish.summary}</strong><br>
                        <small>${channel.publish.description}</small>
                    </div>
                ` : ''}
                ${channel.subscribe ? `
                    <div style="margin: 10px 0;">
                        <span class="operation-method method-subscribe">SUBSCRIBE</span>
                        <strong>${channel.subscribe.summary}</strong><br>
                        <small>${channel.subscribe.description}</small>
                    </div>
                ` : ''}
            </div>
        `;
    }
    container.innerHTML = html || '<p>No channels found.</p>';
}

function renderOperations() {
    const container = document.getElementById('operations-content');
    const channels = asyncApiSpec.channels || {};
    
    let html = '';
    for (const [path, channel] of Object.entries(channels)) {
        if (channel.publish) {
            html += `
                <div class="operation">
                    <div class="operation-header">
                        <span class="operation-method method-publish">PUBLISH</span>
                        ${channel.publish.operationId || 'PublishOperation'}
                    </div>
                    <p><strong>Channel:</strong> ${path}</p>
                    <p><strong>Summary:</strong> ${channel.publish.summary}</p>
                    <p><strong>Description:</strong> ${channel.publish.description}</p>
                    ${channel.publish.tags ? `<p><strong>Tags:</strong> ${channel.publish.tags.map(t => t.name).join(', ')}</p>` : ''}
                </div>
            `;
        }
        if (channel.subscribe) {
            html += `
                <div class="operation">
                    <div class="operation-header">
                        <span class="operation-method method-subscribe">SUBSCRIBE</span>
                        ${channel.subscribe.operationId || 'SubscribeOperation'}
                    </div>
                    <p><strong>Channel:</strong> ${path}</p>
                    <p><strong>Summary:</strong> ${channel.subscribe.summary}</p>
                    <p><strong>Description:</strong> ${channel.subscribe.description}</p>
                    ${channel.subscribe.tags ? `<p><strong>Tags:</strong> ${channel.subscribe.tags.map(t => t.name).join(', ')}</p>` : ''}
                </div>
            `;
        }
    }
    container.innerHTML = html || '<p>No operations found.</p>';
}

function resolveRef(ref) {
    // Resolve $ref like "#/$defs/BinaryAudioSessionMessage"
    if (!ref.startsWith('#/')) return null;
    const path = ref.substring(2).split('/');
    let current = asyncApiSpec;
    for (const segment of path) {
        current = current?.[segment];
        if (!current) return null;
    }
    return current;
}

function renderProperty(propName, prop, depth = 0) {
    const indent = '  '.repeat(depth);
    let typeInfo = prop.type || 'unknown';
    let expandable = false;
    let expandedContent = '';
    
    if (prop.$ref) {
        const resolved = resolveRef(prop.$ref);
        if (resolved) {
            typeInfo = `$ref → ${prop.$ref.split('/').pop()}`;
            expandable = true;
            expandedContent = renderSchemaProperties(resolved, depth + 1);
        } else {
            typeInfo = `$ref → ${prop.$ref}`;
        }
    } else if (prop.type === 'array' && prop.items?.$ref) {
        const resolved = resolveRef(prop.items.$ref);
        if (resolved) {
            typeInfo = `array of ${prop.items.$ref.split('/').pop()}`;
            expandable = true;
            expandedContent = renderSchemaProperties(resolved, depth + 1);
        }
    } else if (prop.type === 'object' && prop.properties) {
        expandable = true;
        expandedContent = renderSchemaProperties(prop, depth + 1);
    }
    
    const expandIcon = expandable ? '<span class="expand-icon" onclick="toggleExpand(this)">▶</span>' : '';
    
    return `
        <div class="schema-prop" style="margin-left: ${depth * 20}px;">
            ${expandIcon}
            <span class="prop-name">${propName}</span>
            <span class="prop-type">(${typeInfo})</span>
            ${prop.description ? `<br><small>${prop.description}</small>` : ''}
            ${prop.example !== undefined ? `<br><code>Example: ${JSON.stringify(prop.example)}</code>` : ''}
            ${expandable ? `<div class="expandable-content" style="display: none;">${expandedContent}</div>` : ''}
        </div>
    `;
}

function renderSchemaProperties(schema, depth = 0) {
    const properties = schema.properties || {};
    return Object.entries(properties).map(([name, prop]) => 
        renderProperty(name, prop, depth)
    ).join('');
}

function toggleExpand(element) {
    const content = element.parentElement.querySelector('.expandable-content');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        element.textContent = '▼';
    } else {
        content.style.display = 'none';
        element.textContent = '▶';
    }
}

function renderSchemas() {
    const container = document.getElementById('schemas-content');
    const messages = asyncApiSpec.components?.messages || {};
    
    let html = '';
    for (const [name, message] of Object.entries(messages)) {
        const payload = message.payload || {};
        const properties = payload.properties || {};
        const defs = payload.$defs || {};
        
        html += `
            <div class="operation">
                <div class="operation-header">📋 ${name}</div>
                <p><strong>Title:</strong> ${message.title || name}</p>
                ${message.description ? `<p><strong>Description:</strong> ${message.description}</p>` : ''}
                
                ${Object.keys(properties).length > 0 ? `
                    <div style="margin-top: 15px;">
                        <strong>Properties:</strong>
                        ${renderSchemaProperties(payload)}
                    </div>
                ` : ''}
                
                ${Object.keys(defs).length > 0 ? `
                    <div style="margin-top: 15px;">
                        <strong>Referenced Schemas:</strong>
                        ${Object.entries(defs).map(([defName, defSchema]) => `
                            <div style="margin: 10px 0; padding: 10px; background: #f0f0f0; border-radius: 4px;">
                                <strong>${defName}:</strong>
                                ${defSchema.description ? `<br><small>${defSchema.description}</small><br>` : ''}
                                ${renderSchemaProperties(defSchema)}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
    container.innerHTML = html || '<p>No message schemas found.</p>';
}

function renderServers() {
    const container = document.getElementById('servers-content');
    const servers = asyncApiSpec.servers || {};
    
    let html = '';
    for (const [name, server] of Object.entries(servers)) {
        html += `
            <div class="operation">
                <div class="operation-header">🖥️ ${name}</div>
                <p><strong>URL:</strong> <code>${server.url}</code></p>
                <p><strong>Protocol:</strong> ${server.protocol}</p>
                ${server.description ? `<p><strong>Description:</strong> ${server.description}</p>` : ''}
                ${server.variables ? `
                    <div style="margin-top: 10px;">
                        <strong>Variables:</strong>
                        ${Object.entries(server.variables).map(([varName, varData]) => `
                            <div class="schema-prop">
                                <span class="prop-name">${varName}</span>: 
                                <span class="prop-type">${varData.default}</span>
                                ${varData.description ? `<br><small>${varData.description}</small>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
    container.innerHTML = html || '<p>No server information found.</p>';
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load AsyncAPI spec and render
    fetch('/asyncapi.json')
        .then(response => response.json())
        .then(spec => {
            asyncApiSpec = spec;
            console.log('AsyncAPI version:', spec.asyncapi);
            
            // Render all sections
            renderChannels();
            renderOperations();
            renderSchemas();
            renderServers();
            
            // Show first section by default
            showSection('channels');
        })
        .catch(error => {
            console.error('Failed to load AsyncAPI spec:', error);
            const loadingElement = document.querySelector('.loading');
            if (loadingElement) {
                loadingElement.textContent = 'Failed to load AsyncAPI documentation.';
            }
        });
});
