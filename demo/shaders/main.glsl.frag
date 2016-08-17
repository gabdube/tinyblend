#version 330

in vec3 vert_color;
out vec4 frag_Color;

void main() 
{
  frag_Color = vec4(vert_color, 1.0);
}