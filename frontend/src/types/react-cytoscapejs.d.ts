declare module 'react-cytoscapejs' {
  import { Component } from 'react';
  import cytoscape from 'cytoscape';
  
  interface CytoscapeComponentProps {
    elements?: cytoscape.ElementDefinition[];
    style?: React.CSSProperties;
    stylesheet?: cytoscape.Stylesheet[];
    layout?: cytoscape.LayoutOptions;
    cy?: (cy: cytoscape.Core) => void;
    [key: string]: any;
  }
  
  export default class CytoscapeComponent extends Component<CytoscapeComponentProps> {}
}
