import React from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import type { Core } from 'cytoscape';

const DEFAULT_STYLESHEET: any[] = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      label: 'data(label)',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 6,
      'text-wrap': 'ellipsis',
      'text-max-width': '100px',
      width: 'mapData(degree, 0, 20, 28, 56)',
      height: 'mapData(degree, 0, 20, 28, 56)',
      'border-width': 2,
      'border-color': 'data(borderColor)',
      'overlay-padding': 4,
    } as any,
  },
  {
    selector: 'node.conflict',
    style: {
      'border-width': 3,
      'border-color': '#F43F5E',
      'border-style': 'double',
    } as any,
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': 'data(color)',
      'line-style': 'data(lineStyle)',
      'target-arrow-color': 'data(color)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      label: 'data(label)',
      'font-size': '9px',
      'text-rotation': 'autorotate',
      'text-margin-y': -10,
      'text-background-color': '#ffffff',
      'text-background-opacity': 0.85,
      'text-background-padding': '2px',
      'text-background-shape': 'roundrectangle',
      color: '#78716C',
      'text-wrap': 'ellipsis',
      'text-max-width': '80px',
    } as any,
  },
  {
    selector: 'edge.conflict-edge',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [8, 4],
      'line-color': '#F43F5E',
      'target-arrow-color': '#F43F5E',
      'text-background-color': '#FEF2F2',
      color: '#F43F5E',
      width: 3,
    } as any,
  },
  {
    selector: '.faded',
    style: { opacity: 0.15 },
  },
  {
    selector: ':selected',
    style: { 'border-width': 4, 'border-color': '#4F46E5' } as any,
  },
];

interface GraphCanvasProps {
  elements: any[];
  stylesheet?: any[];
  onInit?: (cy: Core) => void;
  style?: React.CSSProperties;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  elements,
  stylesheet = DEFAULT_STYLESHEET,
  onInit,
  style = { width: '100%', height: '100%' },
}) => {
  if (elements.length === 0) return null;

  return (
    <CytoscapeComponent
      elements={elements}
      stylesheet={stylesheet}
      style={style}
      layout={{
        name: 'cose',
        animate: true,
        animationDuration: 1000,
        nodeRepulsion: () => 10000,
        idealEdgeLength: () => 150,
        gravity: 0.25,
        numIter: 2000,
        nestingFactor: 1.2,
        nodeOverlap: 20,
      } as any}
      onInit={onInit}
      minZoom={0.2}
      maxZoom={4}
    />
  );
};
