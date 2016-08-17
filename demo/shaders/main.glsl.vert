#version 330

layout (location = 0) in vec3 position;
layout (location = 1) in vec3 color;

out vec3 vert_color;

uniform mat4 view;
uniform mat4 model;
uniform mat4 proj;


void main() 
{
	vert_color = inColor;
	gl_Position = proj * view * model * vec4(inPos.xyz, 1.0);
}