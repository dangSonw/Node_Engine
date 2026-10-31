struct Output { float2 UV : TEXCOORD0; float4 Position : SV_Position; };
Output main(uint vertex : SV_VertexID) {
    Output result;
    result.UV = float2((vertex << 1) & 2, vertex & 2);
    result.Position = float4(result.UV.x * 2 - 1, 1 - result.UV.y * 2, 0, 1);
    return result;
}
