# Libavoid Edge Routing Pro Example

This example shows how to set up and use [libavoid](https://github.com/Aksem/libavoid-js),
a C++ library compiled to WebAssembly, to calculate edge paths that do not
intersect with other nodes in the flow.

The two most important parts of the example are the `<RouteableEdge />` component
and the `useLibavoid()` hook. A custom edge is necessary to draw a path through
arbitrary points: by providing the points as edge data, libavoid (or other edge
routing solutions like Dagre) can inject the edge path can be updated whenever
the routing algorithm runs.

Additionally, we show how to work with dynamically placed handles by looking up
their position in `node.internals.handleBounds`. This is useful when you have
handles positioned using CSS layouts like flexbox or grid, rather than absolute
x/y placement.
